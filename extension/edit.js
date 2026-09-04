// edit.js — resume markdown editor
// Opens as a full tab via chrome.runtime.getURL("edit.html")?variant=<id>

const params    = new URLSearchParams(location.search);
const variantId = params.get("variant");

const editor   = document.getElementById("editor");
const saveBtn  = document.getElementById("save-btn");
const htmlLink = document.getElementById("html-link");
const pdfLink  = document.getElementById("pdf-link");
const statusEl = document.getElementById("status");

if (!variantId) {
  editor.value = "No variant ID in URL. Open this page from the extension panel.";
  saveBtn.disabled = true;
} else {
  htmlLink.href = `${BASE_URL}/variants/${variantId}/html`;
  pdfLink.href  = `${BASE_URL}/variants/${variantId}/pdf`;
  load();
}

async function load() {
  setStatus("Loading...");
  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/markdown`);
    if (!res.ok) { setStatus("Could not load markdown (" + res.status + ")"); return; }
    editor.value = await res.text();
    setStatus("");
  } catch (e) {
    setStatus("Error: " + e.message);
  }
}

saveBtn.addEventListener("click", async () => {
  saveBtn.disabled = true;
  setStatus("Regenerating...");

  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/regenerate`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ markdown: editor.value })
    });

    const result = await res.json();

    if (result.status === "ok") {
      setStatus("Rebuilt — reload View HTML to see changes.");
    } else {
      setStatus("Error: " + JSON.stringify(result));
    }
  } catch (e) {
    setStatus("Error: " + e.message);
  } finally {
    saveBtn.disabled = false;
  }
});

function setStatus(msg) {
  statusEl.textContent = msg;
}
