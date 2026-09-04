// panel.js


let currentJobId     = null;
let currentVariantId = null;
let pollInterval     = null;
let extractedUrl     = "";
let extractedATS     = null;
let extractedCompany = null;
let lastKnownTabUrl  = "";
let allJobs          = [];
let allVariants      = [];

const captureSection   = document.getElementById("capture-section");
const previewSection   = document.getElementById("preview-section");
const ingestBtn        = document.getElementById("ingest-btn");
const urlInput         = document.getElementById("url-input");
const urlIngestBtn     = document.getElementById("url-ingest-btn");
const categorySelect   = document.getElementById("category-select");
const titleInput       = document.getElementById("title-input");
const companyInput     = document.getElementById("company-input");
const descriptionArea  = document.getElementById("description-area");
const atsBadge         = document.getElementById("ats-badge");
const confirmBtn       = document.getElementById("confirm-btn");
const jobInfo          = document.getElementById("job-info");
const jobTitle         = document.getElementById("job-title");
const jobCompany       = document.getElementById("job-company");
const jobUrlLink       = document.getElementById("job-url-link");
const jobTrack         = document.getElementById("job-track");
const generateBtn      = document.getElementById("generate-btn");
const statusEl         = document.getElementById("status");
const linksEl          = document.getElementById("links");
const htmlLink         = document.getElementById("html-link");
const pdfLink          = document.getElementById("pdf-link");
const editLink         = document.getElementById("edit-link");
const jdActualBtn      = document.getElementById("jd-actual-btn");
const fillFormBtn      = document.getElementById("fill-form-btn");
const jobTextToggle    = document.getElementById("job-text-toggle");
const jobTextSection   = document.getElementById("job-text-section");
const jobTextArea      = document.getElementById("job-text-area");
const trackingLink     = document.getElementById("tracking-link");
const refreshBtn       = document.getElementById("refresh-btn");
const searchInput      = document.getElementById("search-input");
const searchClearBtn   = document.getElementById("search-clear-btn");
const clSection        = document.getElementById("cl-section");
const clGenerateBtn    = document.getElementById("cl-generate-btn");
const clStatus         = document.getElementById("cl-status");
const clOutput         = document.getElementById("cl-output");
const clearJobBtn      = document.getElementById("clear-job-btn");
const clTextArea       = document.getElementById("cl-text-area");
const clBrief          = document.getElementById("cl-brief");
const resumePreviewToggle = document.getElementById("resume-preview-toggle");
const resumePreviewFrame  = document.getElementById("resume-preview-frame");
const rewriteBtn          = document.getElementById("rewrite-btn");
const chunkReviewBtn      = document.getElementById("chunk-review-btn");
const roleMatchBadge      = document.getElementById("role-match-badge");
const regenBtn            = document.getElementById("regen-btn");
const clToneBtns          = document.querySelectorAll(".cl-tone-btn");
const clViewLink          = document.getElementById("cl-view-link");
const clViewCombinedLink  = document.getElementById("cl-view-combined-link");
const clDownloadBtn       = document.getElementById("cl-download-btn");
const clDownloadPdf       = document.getElementById("cl-download-pdf-btn");
const clDownloadDocx      = document.getElementById("cl-download-docx-btn");
const clDownloadCombined  = document.getElementById("cl-download-combined-btn");
const dcvTs            = document.getElementById("dcv-ts");
const dcvStatus        = document.getElementById("dcv-status");
const dcvChunkReview   = document.getElementById("dcv-chunk-review");
const dcvHtml          = document.getElementById("dcv-html");
const dcvPdf           = document.getElementById("dcv-pdf");
const dcvRegen         = document.getElementById("dcv-regen");

let currentCLTone = "professional";

trackingLink.href = chrome.runtime.getURL("tracking.html");

// Theme is handled by theme-picker.js (loaded before this script).

// -------------------------------------------------------
// Central scope — every path that puts a job in the main
// panel view goes through here
// -------------------------------------------------------
function scopeToJob(job, variant) {
  clearInterval(pollInterval);
  currentJobId     = job.job_id;
  currentVariantId = variant ? variant.id : null;

  jobCompany.textContent = job.company || "";
  jobTitle.textContent   = job.title || "Untitled";
  jobTrack.textContent = `${job.track || "?"} / ${job.focus || "?"}`;

  if (job.url) {
    jobUrlLink.href = job.url;
    jobUrlLink.classList.remove("hidden");
  } else {
    jobUrlLink.classList.add("hidden");
  }

  // jd_actual.txt is written at ingest time, independent of resume generation —
  // show it as soon as a job is in scope, not gated behind a variant existing.
  jdActualBtn.href = `${BASE_URL}/jobs/${job.job_id}/jd-actual`;
  jdActualBtn.classList.remove("hidden");

  // Reset job text and resume preview
  jobTextSection.classList.add("hidden");
  jobTextArea.value = "";
  jobTextToggle.textContent = "▶ Job text";
  resumePreviewFrame.style.display = "none";
  resumePreviewFrame.removeAttribute("src");
  resumePreviewToggle.textContent = "▶ Preview in panel";
  rewriteBtn.classList.add("hidden");
  chunkReviewBtn.classList.add("hidden");
  regenBtn.classList.add("hidden");
  roleMatchBadge.classList.add("hidden");

  captureSection.classList.add("hidden");
  previewSection.classList.add("hidden");
  jobInfo.classList.remove("hidden");
  clSection.classList.remove("hidden");
  clStatus.textContent = "";
  clOutput.classList.add("hidden");
  clTextArea.value = "";

  // Load saved cover letter for current tone without blocking scope render
  const scopedId = job.job_id;
  fetch(`${BASE_URL}/jobs/${scopedId}/cover_letter?tone=${currentCLTone}`)
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (data?.text && currentJobId === scopedId) {
        clTextArea.value = data.text;
        clOutput.classList.remove("hidden");
        clViewLink.href = `${BASE_URL}/jobs/${scopedId}/cover_letter/html?tone=${currentCLTone}`;
        clViewCombinedLink.href = `${BASE_URL}/jobs/${scopedId}/cover_letter/combined_pdf?tone=${currentCLTone}`;
        clStatus.textContent = `Saved (${currentCLTone})`;
      }
    })
    .catch(() => {});

  if (job.role_match != null) {
    showRoleMatchBadge(job.role_match);
  }

  if (variant) {
    generateBtn.classList.add("hidden");
    htmlLink.href  = `${BASE_URL}/variants/${variant.id}/html`;
    pdfLink.href   = `${BASE_URL}/variants/${variant.id}/pdf`;
    editLink.href  = chrome.runtime.getURL("edit.html") + `?variant=${variant.id}`;
    rewriteBtn.classList.remove("hidden");
    chunkReviewBtn.classList.remove("hidden");
    regenBtn.classList.remove("hidden");
    linksEl.classList.remove("hidden");
    setStatus("Ready.");
  } else if (job.status === "generating") {
    generateBtn.classList.add("hidden");
    linksEl.classList.add("hidden");
    setStatus("Generating…");
    pollJobStatus();
  } else if (job.status === "done") {
    // Variant missing from stale allVariants — re-fetch once before giving up
    const scopedId = job.job_id;
    fetch(`${BASE_URL}/variants/`)
      .then(r => r.json())
      .then(freshVariants => {
        if (currentJobId !== scopedId) return;
        const v = freshVariants.find(v => v.job_id === scopedId);
        if (v) {
          allVariants = freshVariants;
          currentVariantId = v.id;
          htmlLink.href  = `${BASE_URL}/variants/${v.id}/html`;
          pdfLink.href   = `${BASE_URL}/variants/${v.id}/pdf`;
          editLink.href  = chrome.runtime.getURL("edit.html") + `?variant=${v.id}`;
          rewriteBtn.classList.remove("hidden");
          chunkReviewBtn.classList.remove("hidden");
          regenBtn.classList.remove("hidden");
          linksEl.classList.remove("hidden");
          generateBtn.classList.add("hidden");
          setStatus("Ready.");
        } else {
          generateBtn.classList.remove("hidden");
          generateBtn.disabled = false;
          linksEl.classList.add("hidden");
          setStatus("");
        }
      })
      .catch(() => {
        generateBtn.classList.remove("hidden");
        generateBtn.disabled = false;
        linksEl.classList.add("hidden");
        setStatus("");
      });
  } else {
    generateBtn.classList.remove("hidden");
    generateBtn.disabled = false;
    linksEl.classList.add("hidden");
    setStatus("");
  }
}

function resetToCapture() {
  clearInterval(pollInterval);
  currentJobId     = null;
  currentVariantId = null;
  captureSection.classList.remove("hidden");
  previewSection.classList.add("hidden");
  jobInfo.classList.add("hidden");
  linksEl.classList.add("hidden");
  clSection.classList.add("hidden");
  generateBtn.classList.remove("hidden");
  generateBtn.disabled = false;
  setStatus("");
}

clearJobBtn.addEventListener("click", resetToCapture);

// -------------------------------------------------------
// Default CV
// -------------------------------------------------------
async function loadDefaultCv() {
  try {
    const res  = await fetch(`${BASE_URL}/default-cv/status`);
    const data = await res.json();
    if (!res.ok || !data.ready) {
      dcvTs.textContent = "not generated yet";
      [dcvChunkReview, dcvHtml, dcvPdf].forEach(el => el.classList.add("hidden"));
      return;
    }
    const d = new Date(data.last_generated);
    const ts = isNaN(d) ? data.last_generated : d.toLocaleDateString("en-CA", { month: "short", day: "numeric" });
    dcvTs.textContent = `${data.chunk_count} chunks · ${ts}`;
    dcvHtml.href = `${BASE_URL}/variants/default/html`;
    dcvPdf.href  = `${BASE_URL}/variants/default/pdf`;
    [dcvChunkReview, dcvHtml, dcvPdf].forEach(el => el.classList.remove("hidden"));
  } catch (_) {
    dcvTs.textContent = "server offline";
  }
}

dcvChunkReview.addEventListener("click", (e) => {
  e.preventDefault();
  const url = chrome.runtime.getURL("chunk_review.html") + "?variant=default";
  chrome.tabs.create({ url });
});

dcvRegen.addEventListener("click", async () => {
  if (!confirm("Regenerate default CV?\nThis re-selects chunks by priority and rewrites the output.")) return;
  dcvRegen.disabled = true;
  dcvStatus.textContent = "Generating…";
  try {
    const res  = await fetch(`${BASE_URL}/default-cv/generate`, { method: "POST" });
    const data = await res.json();
    if (!res.ok || data.status !== "ok") {
      dcvStatus.textContent = "Error — check server log.";
    } else {
      dcvStatus.textContent = "";
      await loadDefaultCv();
    }
  } catch (_) {
    dcvStatus.textContent = "Failed — server unreachable.";
  } finally {
    dcvRegen.disabled = false;
  }
});

// -------------------------------------------------------
// General-purpose CVs (any job with no company — not hardcoded to a
// specific variant ID, works for however many general CVs you've made)
// -------------------------------------------------------
function renderGeneralCvs() {
  const container = document.getElementById("general-cvs-list");
  if (!container) return;
  container.innerHTML = "";

  const map = buildVariantMap();
  const generalJobs = allJobs.filter(j =>
    j.job_id !== "default-cv" && (!j.company || j.company === "—")
  );

  for (const job of generalJobs) {
    const v = map[job.job_id];
    if (!v) continue;
    const row = document.createElement("div");
    row.className = "dcv-row";
    row.style.marginTop = "4px";
    row.innerHTML = `
      <span class="dcv-label">${job.title || job.job_id}</span>
      <a class="dcv-link" href="#" title="Chunk Review" data-variant="${v.id}">⊞ Chunks</a>
      <a class="dcv-link" href="${BASE_URL}/variants/${v.id}/html" target="_blank" title="View HTML">HTML</a>
      <a class="dcv-link" href="${BASE_URL}/variants/${v.id}/pdf" target="_blank" title="Download PDF">PDF</a>
    `;
    row.querySelector('[data-variant]').addEventListener("click", (e) => {
      e.preventDefault();
      const url = chrome.runtime.getURL("chunk_review.html") + `?variant=${v.id}`;
      chrome.tabs.create({ url });
    });
    container.appendChild(row);
  }
}

// -------------------------------------------------------
// Job text toggle
// -------------------------------------------------------
jobTextToggle.addEventListener("click", async () => {
  if (!currentJobId) return;
  const isOpen = !jobTextSection.classList.contains("hidden");
  if (isOpen) {
    jobTextSection.classList.add("hidden");
    jobTextToggle.textContent = "▶ Job text";
    return;
  }
  jobTextToggle.textContent = "▾ Job text";
  jobTextSection.classList.remove("hidden");
  if (!jobTextArea.value) {
    jobTextArea.value = "Loading…";
    try {
      const res = await fetch(`${BASE_URL}/jobs/${currentJobId}`);
      const job = await res.json();
      jobTextArea.value = job.raw_text || "(no text stored)";
    } catch (_) {
      jobTextArea.value = "Error loading job text.";
    }
  }
});

// -------------------------------------------------------
// ATS detection
// -------------------------------------------------------
function detectATS(url) {
  if (!url) return null;
  if (url.includes("boards.greenhouse.io") || url.includes("greenhouse.io/jobs")) return "greenhouse";
  if (url.includes("jobs.lever.co") || url.includes(".lever.co/")) return "lever";
  return null;
}

// -------------------------------------------------------
// Step 1: Extract — shared preview population
// -------------------------------------------------------
async function populatePreview(data, resetBtn) {
  extractedUrl     = data.url;
  extractedATS     = detectATS(data.url);
  extractedCompany = extractCompany(data.title, data.og_site_name || "");
  titleInput.value   = cleanTitle(data.title);
  companyInput.value = extractedCompany || "";

  try {
    const cleanRes  = await fetch(`${BASE_URL}/jobs/clean_preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: data.raw_text })
    });
    const cleanData = await cleanRes.json();
    descriptionArea.value = cleanData.cleaned_text || data.raw_text;
  } catch (_) {
    descriptionArea.value = data.raw_text;
  }

  if (extractedATS) {
    atsBadge.textContent = extractedATS.charAt(0).toUpperCase() + extractedATS.slice(1) + " detected — clean fill available";
    atsBadge.classList.remove("hidden");
  } else {
    atsBadge.classList.add("hidden");
  }

  captureSection.classList.add("hidden");
  previewSection.classList.remove("hidden");
  if (resetBtn) resetBtn.disabled = false;
  setStatus("");
}

ingestBtn.addEventListener("click", () => {
  setStatus("Capturing...");
  ingestBtn.disabled = true;

  chrome.runtime.sendMessage({ type: "extract_only" }, async (data) => {
    if (chrome.runtime.lastError || !data) {
      setStatus("Error: Could not capture. Try reloading the tab.");
      ingestBtn.disabled = false;
      return;
    }
    if (data.error) {
      setStatus("Error: " + data.error);
      ingestBtn.disabled = false;
      return;
    }
    await populatePreview(data, ingestBtn);
  });
});

// URL-based capture — opens tab in background, extracts, closes it
urlIngestBtn.addEventListener("click", () => captureFromUrl());
urlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") captureFromUrl(); });

function captureFromUrl() {
  const url = urlInput.value.trim();
  if (!url) return;
  setStatus("Opening popup to capture — window will close automatically…");
  urlIngestBtn.disabled = true;

  chrome.runtime.sendMessage({ type: "capture_from_url", url }, async (data) => {
    urlIngestBtn.disabled = false;
    if (chrome.runtime.lastError || !data) {
      setStatus("Error: Could not capture from URL.");
      return;
    }
    if (data.error) {
      setStatus("Error: " + data.error);
      return;
    }
    urlInput.value = "";
    await populatePreview(data, null);
  });
}

function cleanTitle(raw) {
  return raw
    .replace(/^Job Application for\s+/i, "")
    .replace(/\s*\|.*$/i, "")   // strip " | Platform" suffix (any board)
    .replace(/\s*[-–]\s*(LinkedIn|Indeed|Glassdoor|ZipRecruiter|Jobright\.ai)\s*$/i, "")
    .trim();
}

const JOB_BOARD_NAMES = /^(linkedin|indeed|glassdoor|ziprecruiter|monster|careerbuilder|dice|simplyhired|workday|angellist|wellfound|handshake|builtin|lever|greenhouse)$/i;

function extractCompany(rawTitle, ogSiteName = "") {
  // og:site_name is most reliable on direct company career pages
  if (ogSiteName && !JOB_BOARD_NAMES.test(ogSiteName.trim())) return ogSiteName.trim();
  // Greenhouse: "Job Application for Title at Company"
  const gh = rawTitle.match(/^Job Application for .+ at (.+?)(?:\s*[-|]|$)/i);
  if (gh) return gh[1].trim();
  // LinkedIn: "Title | Company | LinkedIn"
  const parts = rawTitle.split("|").map(s => s.trim());
  if (parts.length >= 3 && /linkedin/i.test(parts[parts.length - 1])) return parts[1];
  // Indeed: "Title - Company - City, State - Indeed"
  if (/indeed/i.test(rawTitle)) {
    const segs = rawTitle.split(/\s*[-–]\s*/);
    if (segs.length >= 2) return segs[1].trim();
  }
  // Glassdoor: "Title at Company | Glassdoor"
  if (/glassdoor/i.test(rawTitle)) {
    const m = rawTitle.match(/\bat\s+([^|]+?)(?:\s*\||$)/i);
    if (m) return m[1].trim();
  }
  // Generic "Title at Company Name"
  const at = rawTitle.match(/\bat\s+([A-Z][^|\-\n]+?)(?:\s*[-|]|$)/);
  if (at) return at[1].trim();
  return null;
}

// -------------------------------------------------------
// Step 2: Confirm & save
// -------------------------------------------------------
confirmBtn.addEventListener("click", async () => {
  const company = companyInput.value.trim();
  if (!company) {
    setStatus("Company is required — enter the employer name before saving.");
    return;
  }

  setStatus("Saving job...");
  confirmBtn.disabled = true;

  try {
    const title = cleanTitle(titleInput.value.trim());

    const res = await fetch(`${BASE_URL}/jobs/ingest`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        raw_text:     descriptionArea.value,
        url:          extractedUrl,
        title,
        company,
        job_category: categorySelect?.value || "Main",
      })
    });

    const result = await res.json();
    confirmBtn.disabled = false;

    if (result.error || result.detail) {
      setStatus("Error: " + (result.error || result.detail));
      return;
    }

    const syntheticJob = {
      job_id:     result.job_id,
      title,
      company,
      track:      result.track,
      focus:      result.focus,
      url:        extractedUrl,
      status:     result.status || "ingested",
      role_match: result.role_match ?? null
    };

    let variant = null;
    if (result.duplicate) {
      const varRes   = await fetch(`${BASE_URL}/variants/`);
      const variants = await varRes.json();
      variant = variants.find(v => v.job_id === result.job_id) || null;
      setStatus("Already saved.");
    }

    scopeToJob(syntheticJob, variant);
    loadRecentJobs();

  } catch (e) {
    setStatus("Error: " + e.message);
    confirmBtn.disabled = false;
  }
});

// -------------------------------------------------------
// Step 3: Generate
// -------------------------------------------------------
generateBtn.addEventListener("click", () => {
  if (!currentJobId) return;
  setStatus("Queued — generating resume...");
  generateBtn.disabled = true;

  fetch(`${BASE_URL}/jobs/${currentJobId}/generate`, { method: "POST" })
    .then(async r => {
      const result = await r.json();
      if (!r.ok || result.error || result.detail) {
        setStatus("Error: " + (result.detail || result.error || r.status));
        generateBtn.disabled = false;
        return;
      }
      if (result.status === "done") {
        onGenerateDone();
      } else {
        pollJobStatus();
      }
    })
    .catch(e => {
      setStatus("Error: " + e.message);
      generateBtn.disabled = false;
    });
});

// -------------------------------------------------------
// Fill form
// -------------------------------------------------------
fillFormBtn.addEventListener("click", () => {
  fillFormBtn.disabled = true;
  fillFormBtn.textContent = "Filling...";
  chrome.runtime.sendMessage({ type: "fill_form" }, (result) => {
    fillFormBtn.disabled = false;
    fillFormBtn.textContent = "Fill Form on Page";
    if (result && result.error) setStatus("Fill error: " + result.error);
    else setStatus("Form filled.");
  });
});

// -------------------------------------------------------
// Resume inline preview toggle
// -------------------------------------------------------
resumePreviewToggle.addEventListener("click", () => {
  const isOpen = resumePreviewFrame.style.display !== "none";
  if (isOpen) {
    resumePreviewFrame.style.display = "none";
    resumePreviewToggle.textContent = "▶ Preview in panel";
  } else {
    resumePreviewFrame.style.display = "block";
    resumePreviewToggle.textContent = "▾ Preview in panel";
    if (htmlLink.getAttribute("href")) {
      resumePreviewFrame.src = htmlLink.href;
    }
  }
});

// -------------------------------------------------------
// Polling
// -------------------------------------------------------
function pollJobStatus() {
  if (!currentJobId) return;
  const jobId = currentJobId;
  clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`${BASE_URL}/jobs/${jobId}`);
      const job = await res.json();
      if (job.status === "done") {
        clearInterval(pollInterval);
        onGenerateDone();
      } else if (job.status === "error") {
        clearInterval(pollInterval);
        setStatus("Generation failed.");
        generateBtn.classList.remove("hidden");
        generateBtn.disabled = false;
      }
    } catch (_) { clearInterval(pollInterval); }
  }, 2000);
}

async function onGenerateDone() {
  try {
    const res      = await fetch(`${BASE_URL}/variants/`);
    const variants = await res.json();
    const variant  = variants.find(v => v.job_id === currentJobId);
    if (!variant) { setStatus("Variant not found."); return; }
    currentVariantId  = variant.id;
    htmlLink.href     = `${BASE_URL}/variants/${variant.id}/html`;
    pdfLink.href      = `${BASE_URL}/variants/${variant.id}/pdf`;
    editLink.href     = chrome.runtime.getURL("edit.html") + `?variant=${variant.id}`;
    generateBtn.classList.add("hidden");
    rewriteBtn.classList.remove("hidden");
    chunkReviewBtn.classList.remove("hidden");
    regenBtn.classList.remove("hidden");
    regenBtn.disabled = false;
    linksEl.classList.remove("hidden");
    setStatus("Done.");
    loadRecentJobs();
  } catch (e) { setStatus("Error loading output: " + e.message); }
}

// -------------------------------------------------------
// Role match badge helper
// -------------------------------------------------------

function showRoleMatchBadge(score) {
  if (score == null) { roleMatchBadge.classList.add("hidden"); return; }
  let cls, text;
  if (score >= 0.75)       { cls = "strong";   text = "Strong match"; }
  else if (score >= 0.58)  { cls = "possible"; text = "Possible match"; }
  else                     { cls = "outside";  text = "Outside target"; }
  roleMatchBadge.className = `role-match-badge ${cls}`;
  roleMatchBadge.textContent = text;
  roleMatchBadge.classList.remove("hidden");
}

// -------------------------------------------------------
// Rewrite — opens full-page review tab
// -------------------------------------------------------

rewriteBtn.addEventListener("click", () => {
  if (!currentVariantId) return;
  const url = chrome.runtime.getURL("rewrite.html")
    + `?variant=${encodeURIComponent(currentVariantId)}`
    + `&job=${encodeURIComponent(currentJobId)}`;
  chrome.tabs.create({ url });
});

// -------------------------------------------------------
// Chunk Review — opens full-page chunk review tab
// -------------------------------------------------------

chunkReviewBtn.addEventListener("click", () => {
  if (!currentVariantId) return;
  const url = chrome.runtime.getURL("chunk_review.html")
    + `?variant=${encodeURIComponent(currentVariantId)}`;
  chrome.tabs.create({ url });
});

regenBtn.addEventListener("click", async () => {
  if (!currentJobId) return;
  const msg = `Re-generate resume for this job?\nThis replaces the existing output.`;
  if (!confirm(msg)) return;
  regenBtn.disabled = true;
  generateBtn.classList.add("hidden");
  linksEl.classList.add("hidden");
  setStatus("Regenerating…");
  try {
    const res = await fetch(`${BASE_URL}/jobs/${currentJobId}/generate?force=true`, { method: "POST" });
    const result = await res.json();
    if (result.status === "generating") pollJobStatus();
  } catch (_) {
    regenBtn.disabled = false;
    setStatus("Re-generate failed.");
  }
});

// -------------------------------------------------------
// Cover letter
// -------------------------------------------------------
clToneBtns.forEach(btn => {
  btn.addEventListener("click", async () => {
    clToneBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentCLTone = btn.dataset.tone;
    clOutput.classList.add("hidden");
    clTextArea.value = "";
    clStatus.textContent = "";
    if (!currentJobId) return;
    try {
      const res = await fetch(`${BASE_URL}/jobs/${currentJobId}/cover_letter?tone=${currentCLTone}`);
      if (res.ok) {
        const data = await res.json();
        clTextArea.value = data.text;
        clOutput.classList.remove("hidden");
        clViewLink.href = `${BASE_URL}/jobs/${currentJobId}/cover_letter/html?tone=${currentCLTone}`;
        clViewCombinedLink.href = `${BASE_URL}/jobs/${currentJobId}/cover_letter/combined_pdf?tone=${currentCLTone}`;
        clStatus.textContent = `Saved (${currentCLTone})`;
      }
    } catch (_) {}
  });
});

clDownloadBtn.addEventListener("click", () => {
  const txt = clTextArea.value;
  if (!txt) return;
  const blob = new Blob([txt], { type: "text/plain" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `cover_letter_${currentCLTone}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

clDownloadPdf.addEventListener("click", () => {
  if (!currentJobId) return;
  const a    = document.createElement("a");
  a.href     = `${BASE_URL}/jobs/${currentJobId}/cover_letter/pdf?tone=${currentCLTone}`;
  a.download = `cover_letter_${currentCLTone}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

clDownloadDocx.addEventListener("click", () => {
  if (!currentJobId) return;
  const a    = document.createElement("a");
  a.href     = `${BASE_URL}/jobs/${currentJobId}/cover_letter/docx?tone=${currentCLTone}`;
  a.download = `cover_letter_${currentCLTone}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

clDownloadCombined.addEventListener("click", () => {
  if (!currentJobId) return;
  const a    = document.createElement("a");
  a.href     = `${BASE_URL}/jobs/${currentJobId}/cover_letter/combined_pdf?tone=${currentCLTone}`;
  a.download = `application_${currentCLTone}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
});

clGenerateBtn.addEventListener("click", async () => {
  if (!currentJobId) return;
  clGenerateBtn.disabled = true;
  clGenerateBtn.textContent = "Generating…";
  clStatus.textContent = `Generating (${currentCLTone})…`;
  clOutput.classList.add("hidden");

  try {
    const res  = await fetch(`${BASE_URL}/jobs/${currentJobId}/cover_letter`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ tone: currentCLTone, briefing: clBrief.value.trim() || null })
    });
    const data = await res.json();

    if (!res.ok || data.detail || data.error) {
      clStatus.textContent = "Error: " + (data.detail || data.error || res.status);
    } else {
      clTextArea.value = data.text;
      clOutput.classList.remove("hidden");
      clViewLink.href = `${BASE_URL}/jobs/${currentJobId}/cover_letter/html?tone=${currentCLTone}`;
      clViewCombinedLink.href = `${BASE_URL}/jobs/${currentJobId}/cover_letter/combined_pdf?tone=${currentCLTone}`;
      clStatus.textContent = `Generated (${currentCLTone}) — copy or edit below`;
    }
  } catch (e) {
    clStatus.textContent = "Error: " + e.message;
  } finally {
    clGenerateBtn.disabled = false;
    clGenerateBtn.textContent = "Generate Cover Letter";
  }
});

// -------------------------------------------------------
// Recent jobs — search + render
// -------------------------------------------------------
async function loadRecentJobs(tabUrl = "") {
  try {
    const [jobsRes, variantsRes] = await Promise.all([
      fetch(`${BASE_URL}/jobs/`),
      fetch(`${BASE_URL}/variants/`)
    ]);
    allJobs     = await jobsRes.json();
    allVariants = await variantsRes.json();
    renderJobList();
    renderGeneralCvs();
    if (tabUrl) autoScopeFromUrl(tabUrl);
  } catch (_) { /* API may not be running */ }
}

function buildVariantMap() {
  const m = {};
  for (const v of allVariants) m[v.job_id] = v;
  return m;
}

function renderJobList() {
  const q   = (searchInput.value || "").toLowerCase().trim();
  const map = buildVariantMap();
  const eligible = allJobs.filter(j => j.job_id !== "default-cv");
  const visible = q
    ? eligible.filter(j =>
        (j.title   || "").toLowerCase().includes(q) ||
        (j.company || "").toLowerCase().includes(q) ||
        (j.track   || "").toLowerCase().includes(q))
    : eligible;
  const container = document.getElementById("recent-jobs-list");
  container.innerHTML = "";
  for (const job of visible) container.appendChild(buildJobItem(job, map[job.job_id]));
  if (visible.length === 0 && q) {
    const msg = document.createElement("div");
    msg.style.cssText = "font-size:0.72rem;color:#444;padding:4px 0";
    msg.textContent = "No matches.";
    container.appendChild(msg);
  }
}

searchInput.addEventListener("input", () => {
  searchClearBtn.classList.toggle("hidden", !searchInput.value);
  renderJobList();
});

searchClearBtn.addEventListener("click", () => {
  searchInput.value = "";
  searchClearBtn.classList.add("hidden");
  renderJobList();
});

function normalizeUrl(url) {
  try { const u = new URL(url); u.search = ""; u.hash = ""; return u.toString().replace(/\/$/, ""); }
  catch (_) { return url; }
}

function autoScopeFromUrl(tabUrl) {
  if (!previewSection.classList.contains("hidden")) return;
  const norm  = normalizeUrl(tabUrl);
  const map   = buildVariantMap();
  const match = allJobs.find(j => j.url && normalizeUrl(j.url) === norm);
  if (!match) return;
  if (currentJobId === match.job_id) return;
  scopeToJob(match, map[match.job_id] || null);
}

function buildJobItem(job, variant) {
  const div = document.createElement("div");
  div.className = "job-item";
  div.id = `ji-${job.job_id}`;

  const title      = job.title || "Untitled";
  const shortTitle = title.length > 27 ? title.slice(0, 27) + "…" : title;
  const appLabel   = job.app_status ? ` · ${job.app_status}` : "";
  const date       = job.ingested_at
    ? new Date(job.ingested_at).toLocaleDateString("en-CA", { month: "short", day: "numeric" })
    : "";

  const roleBadgeHtml = (() => {
    const s = job.role_match;
    if (s == null) return "";
    if (s >= 0.75) return `<span class="role-match-badge strong">Strong match</span>`;
    if (s >= 0.58) return `<span class="role-match-badge possible">Possible match</span>`;
    return `<span class="role-match-badge outside">Outside target</span>`;
  })();

  div.innerHTML = `
    <div class="job-item-title-row">
      <span class="job-item-title job-focus-link" title="${esc(title)}">${esc(shortTitle)}</span>
      ${job.url ? `<a class="job-ext-link" href="${esc(job.url)}" target="_blank" title="Open original posting">↗</a>` : ""}
    </div>
    ${job.company ? `<div class="job-item-company">${esc(job.company)}</div>` : ""}
    <div class="job-item-meta">
      <span class="track-chip">${esc(job.track || "?")}</span>
      ${roleBadgeHtml}
      <span class="job-item-date">${date}${esc(appLabel)}</span>
    </div>
    <div class="job-item-actions"></div>
  `;

  div.querySelector(".job-focus-link").addEventListener("click", () => {
    scopeToJob(job, variant || null);
    setStatus("Job in scope.");
  });

  const actions = div.querySelector(".job-item-actions");

  if (variant) {
    actions.append(
      mkBtn("View",   () => window.open(`${BASE_URL}/variants/${variant.id}/html`, "_blank")),
      mkBtn("Edit",   () => window.open(chrome.runtime.getURL("edit.html") + `?variant=${variant.id}`, "_blank")),
      mkBtn("Re-gen", (btn) => regenJob(job, btn, variant)),
      mkBtn("✕",      (btn) => deleteJob(job, btn, variant), "danger")
    );
  } else if (job.status === "generating") {
    const s = document.createElement("span");
    s.style.cssText = "font-size:0.7rem;color:#555";
    s.textContent = "Generating…";
    actions.appendChild(s);
  } else {
    actions.append(
      mkBtn("Generate", (btn) => generateFromList(job, btn), "primary"),
      mkBtn("✕",        (btn) => deleteJob(job, btn), "danger")
    );
  }

  return div;
}

function mkBtn(label, onClick, cls) {
  const btn = document.createElement("button");
  btn.className = "btn-sm" + (cls ? " " + cls : "");
  btn.textContent = label;
  btn.addEventListener("click", () => onClick(btn));
  return btn;
}

async function regenJob(job, btn, variant) {
  const msg = `Re-generate resume for "${job.title}"?\nThis replaces the existing output.`;
  if (!confirm(msg)) return;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const res    = await fetch(`${BASE_URL}/jobs/${job.job_id}/generate?force=true`, { method: "POST" });
    const result = await res.json();
    if (result.status === "generating") {
      if (job.job_id === currentJobId) {
        generateBtn.classList.add("hidden");
        linksEl.classList.add("hidden");
        setStatus("Regenerating…");
        pollJobStatus();
      } else {
        pollJobItem(job.job_id);
      }
    }
  } catch (_) {
    btn.disabled = false;
    btn.textContent = "Re-gen";
  }
}

async function generateFromList(job, btn) {
  btn.disabled = true;
  btn.textContent = "…";
  try {
    await fetch(`${BASE_URL}/jobs/${job.job_id}/generate`, { method: "POST" });
    scopeToJob(job, null);
    pollJobStatus();
  } catch (_) {
    btn.disabled = false;
    btn.textContent = "Generate";
  }
}

function pollJobItem(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`${BASE_URL}/jobs/${jobId}`);
      const job = await res.json();
      if (job.status === "done" || job.status === "error") {
        clearInterval(interval);
        loadRecentJobs();
      }
    } catch (_) { clearInterval(interval); }
  }, 2000);
}

async function deleteJob(job, btn, variant) {
  const msg = `Delete "${job.title || "this job"}" and all output files?\nThis cannot be undone.`;
  if (!confirm(msg)) return;
  btn.disabled = true;
  try {
    await fetch(`${BASE_URL}/jobs/${job.job_id}`, { method: "DELETE" });
    if (job.job_id === currentJobId) resetToCapture();
    loadRecentJobs();
  } catch (e) {
    setStatus("Delete failed: " + e.message);
    btn.disabled = false;
  }
}

// -------------------------------------------------------
// Refresh button + tab-activated auto-scope (via content.js visibilitychange)
// -------------------------------------------------------
refreshBtn.addEventListener("click", () => {
  refreshBtn.style.opacity = "0.4";
  loadRecentJobs(lastKnownTabUrl).finally(() => { refreshBtn.style.opacity = ""; });
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "tab_activated") {
    lastKnownTabUrl = msg.url || "";
    loadRecentJobs(lastKnownTabUrl);
  }
});

// -------------------------------------------------------
// Helpers
// -------------------------------------------------------
function esc(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function setStatus(msg) {
  statusEl.textContent = msg;
}

// -------------------------------------------------------
// Init
// -------------------------------------------------------
loadRecentJobs();
loadDefaultCv();
