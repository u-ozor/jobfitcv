// background.js — MV3 service worker

importScripts("config.js");

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});


// Inject content.js if not present, then send message to tab
function sendToTab(tabId, message, callback) {
  chrome.tabs.sendMessage(tabId, message, (result) => {
    if (!chrome.runtime.lastError && result) { callback(result); return; }
    // Clear stale injection guard before re-injecting (survives extension reloads on the page's window)
    chrome.scripting.executeScript({ target: { tabId }, func: () => { delete window.__jaa_injected; } }, () => {
      chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] }, () => {
        if (chrome.runtime.lastError) { callback({ error: "Cannot inject into this page." }); return; }
        chrome.tabs.sendMessage(tabId, message, (result2) => {
          callback(result2 || { error: "No response from content script." });
        });
      });
    });
  });
}

function extractFromTab(tabId, callback) {
  sendToTab(tabId, { type: "extract" }, (data) => {
    callback((!data || data.error) ? { error: data?.error || "Could not extract page content." } : data);
  });
}

function detectATS(url) {
  if (!url) return null;
  if (url.includes("boards.greenhouse.io") || url.includes("greenhouse.io/jobs")) return "greenhouse";
  if (url.includes("jobs.lever.co") || url.includes(".lever.co/")) return "lever";
  return null;
}

const JD_SELECTORS = [
  ".jobs-description__container",
  "#job-details",
  ".jobs-description-content__text",
  ".job-details__content",
  "#jobDescriptionText",
  ".jobsearch-jobDescriptionText",
].join(",");

// Poll the tab until a known JD container appears (or timeout), then extract.
// Replaces fixed-delay approach — fires as soon as content is ready.
function waitForContent(tabId, maxMs, callback) {
  const start = Date.now();
  const sels = JD_SELECTORS;

  function poll() {
    chrome.scripting.executeScript(
      { target: { tabId }, func: (s) => { const el = document.querySelector(s); return el ? el.innerText.trim().length : 0; }, args: [sels] },
      (results) => {
        if (chrome.runtime.lastError) {
          if (Date.now() - start < maxMs) { setTimeout(poll, 800); return; }
          sendToTab(tabId, { type: "extract" }, callback);
          return;
        }
        const len = results?.[0]?.result ?? 0;
        if (len > 200) {
          // Content found — click "see more" then extract
          chrome.scripting.executeScript(
            { target: { tabId }, func: () => {
              const btn = document.querySelector(".jobs-description__footer-button")
                || document.querySelector("[data-testid='job-expander-button']")
                || [...document.querySelectorAll("button")].find(b => /^(see|show) more$/i.test(b.textContent.trim()));
              if (btn) btn.click();
            }},
            () => { setTimeout(() => sendToTab(tabId, { type: "extract" }, callback), 700); }
          );
        } else if (Date.now() - start < maxMs) {
          setTimeout(poll, 700);
        } else {
          sendToTab(tabId, { type: "extract" }, callback);
        }
      }
    );
  }
  setTimeout(poll, 2500); // initial wait for SPA mount
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {

  if (msg.type === "extract_only") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      extractFromTab(tabs[0].id, sendResponse);
    });
    return true;
  }

  if (msg.type === "generate") {
    fetch(`${BASE_URL}/jobs/${msg.job_id}/generate`, { method: "POST" })
      .then(r => r.json())
      .then(result => sendResponse(result))
      .catch(e => sendResponse({ error: e.message }));
    return true;
  }

  if (msg.type === "capture_from_url") {
    // Open in an unfocused popup window so the tab's visibilityState = 'visible'.
    // active:false background tabs get visibilityState='hidden' — LinkedIn SPA detects
    // this and defers job description rendering entirely, so extraction always misses the JD.
    // A popup window with focused:false keeps user focus on their main window while the tab
    // is the active (foreground) tab within its own window → SPA renders normally.
    chrome.windows.create({ url: msg.url, focused: false, type: "popup", width: 900, height: 700 }, (win) => {
      if (chrome.runtime.lastError || !win) {
        sendResponse({ error: "Could not open capture window." });
        return;
      }
      const tabId = win.tabs[0].id;
      const winId = win.id;
      function onUpdated(tid, changeInfo) {
        if (tid !== tabId || changeInfo.status !== "complete") return;
        chrome.tabs.onUpdated.removeListener(onUpdated);
        waitForContent(tabId, 9000, (data) => {
          chrome.windows.remove(winId);
          sendResponse(data?.error ? { error: data.error } : data);
        });
      }
      chrome.tabs.onUpdated.addListener(onUpdated);
    });
    return true;
  }

  if (msg.type === "fill_form") {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      const tab = tabs[0];
      const ats = detectATS(tab.url || "");
      try {
        const [profileRes, expRes] = await Promise.all([
          fetch(`${BASE_URL}/profile`),
          fetch(`${BASE_URL}/experience`)
        ]);
        const profile    = await profileRes.json();
        const experience = await expRes.json();
        sendToTab(tab.id, { type: "fill_form", profile, experience, ats }, (result) => {
          sendResponse(result || { ok: true });
        });
      } catch (e) { sendResponse({ error: e.message }); }
    });
    return true;
  }

});
