// rewrite.js

const params    = new URLSearchParams(location.search);
const variantId = params.get("variant");
const jobId     = params.get("job");

let allItems          = [];
let activeSection     = "all";
let approvedSet       = new Set();
let beforeBlobUrl     = null;
let currentDiffSource = null;  // null = pending/just-generated, string = diff filename from history

// Theme is handled by theme-picker.js (loaded before this script).

document.getElementById("close-btn").addEventListener("click", () => window.close());

// ── Section tabs ──
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    activeSection = tab.dataset.section;
    renderItems();
  });
});

document.getElementById("rerun-btn").addEventListener("click", runPreview);
document.getElementById("history-select").addEventListener("change", async function () {
  const filename = this.value;
  if (!filename) return;
  setStatus("Loading diff…");
  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/diffs/${encodeURIComponent(filename)}`);
    if (!res.ok) {
      setStatus("Failed to load diff.");
      this.value = "";
      return;
    }
    const data = await res.json();
    loadDiffData(data, filename);
    const rec = approvedSet.size;
    setStatus(
      `Loaded ${allItems.length} rewrite${allItems.length !== 1 ? "s" : ""} from ${filename}.` +
      (rec ? ` ${rec} Recommended pre-selected.` : "")
    );
  } catch (e) {
    setStatus("Error: " + e.message);
    this.value = "";
  }
});
document.getElementById("select-all-btn").addEventListener("click", () => {
  getFiltered().forEach(item => approvedSet.add(item.index));
  renderItems();
});
document.getElementById("apply-btn").addEventListener("click", applyApproved);
document.getElementById("discard-btn").addEventListener("click", discard);

// ── Init ──
async function init() {
  if (!variantId) {
    setStatus("No variant ID — open this page from the panel ↗ button.");
    return;
  }
  await loadJobMeta();
  await cacheBeforeHtml();
  await loadDiffsDropdown();

  // Load pending diff if one exists; only generate fresh if there isn't one
  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/pending`);
    if (res.ok) {
      const data = await res.json();
      loadDiffData(data, null);
      const rec = approvedSet.size;
      setStatus(
        `Pending diff loaded — ${allItems.length} rewrite${allItems.length !== 1 ? "s" : ""} ready.` +
        (rec ? ` ${rec} Recommended pre-selected.` : "")
      );
      return;
    }
  } catch (_) {}

  await runPreview();
}

async function loadJobMeta() {
  if (!jobId) return;
  try {
    const res = await fetch(`${BASE_URL}/jobs/${jobId}`);
    if (!res.ok) return;
    const job = await res.json();
    document.getElementById("job-meta").textContent =
      `${job.title || "Untitled"} · ${job.track || "?"}/${job.focus || "?"}`;
    document.title = `Rewrite — ${job.title || "Untitled"}`;
  } catch (_) {}
}

async function cacheBeforeHtml() {
  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/html`);
    if (!res.ok) return;
    const html = await res.text();
    if (beforeBlobUrl) URL.revokeObjectURL(beforeBlobUrl);
    beforeBlobUrl = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    // Show in right pane as the "current" resume while reviewing
    document.getElementById("resume-frame").src = beforeBlobUrl;
    document.getElementById("right-label").textContent = "Current resume (before)";
  } catch (_) {}
}

// ── History dropdown ──
async function loadDiffsDropdown() {
  const sel = document.getElementById("history-select");
  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/diffs`);
    if (!res.ok) return;
    const diffs = await res.json();
    const current = sel.value;
    sel.innerHTML = `<option value="">History…</option>`;
    diffs.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.filename;
      const ts = d.created_at ? d.created_at.slice(0, 16).replace("T", " ") : "";
      opt.textContent = `${ts} (${d.item_count ?? "?"}, ${d.recommended_count ?? 0} rec)`;
      sel.appendChild(opt);
    });
    // Restore selection if still valid
    if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
  } catch (_) {}
}

// ── Load diff data into the review UI ──
function loadDiffData(data, sourceFilename) {
  currentDiffSource = sourceFilename;
  allItems = data.items || [];
  approvedSet = new Set(
    allItems.filter(i => i.recommend === "recommended").map(i => i.index)
  );
  exitComparisonMode();
  updateCounts();
  renderItems();
  document.getElementById("footer-actions").classList.remove("hidden");
}

// ── Preview fetch ──
async function runPreview() {
  const rerunBtn = document.getElementById("rerun-btn");
  rerunBtn.disabled = true;
  currentDiffSource = null;
  setStatus("Running rewrites — this may take 15–30 seconds…");
  document.getElementById("footer-actions").classList.add("hidden");
  document.getElementById("items-scroll").innerHTML = "";
  clearCounts();
  allItems    = [];
  approvedSet = new Set();

  // Re-cache before in case user re-ran after a prior apply
  await cacheBeforeHtml();
  exitComparisonMode();

  try {
    const res  = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/preview`, { method: "POST" });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) { data = null; }

    if (!res.ok) {
      setStatus("Error: " + (data?.detail || text.slice(0, 200) || res.status));
      return;
    }

    allItems = data.items || [];

    if (!allItems.length) {
      setStatus("No rewrites produced — bullets already well-aligned or all rejected by validator.");
      return;
    }

    // Pre-approve Recommended items (similarity < 0.65)
    approvedSet = new Set(
      allItems.filter(i => i.recommend === "recommended").map(i => i.index)
    );

    updateCounts();
    renderItems();
    const rec = approvedSet.size;
    setStatus(
      `${allItems.length} rewrite${allItems.length !== 1 ? "s" : ""} ready.` +
      (rec ? ` ${rec} Recommended pre-selected.` : "")
    );
    document.getElementById("footer-actions").classList.remove("hidden");
    // Refresh history dropdown so this run's diff appears
    await loadDiffsDropdown();
    document.getElementById("history-select").value = "";
  } catch (e) {
    setStatus("Error: " + e.message);
  } finally {
    rerunBtn.disabled = false;
  }
}

// ── Render items ──
function getFiltered() {
  return activeSection === "all"
    ? allItems
    : allItems.filter(item => item.section === activeSection);
}

function renderItems() {
  const container = document.getElementById("items-scroll");
  container.innerHTML = "";
  const filtered = getFiltered();

  if (!filtered.length) {
    const msg = document.createElement("div");
    msg.className = "empty-msg";
    msg.textContent = allItems.length
      ? "No rewrites in this section."
      : "Run rewrites to see suggestions.";
    container.appendChild(msg);
    return;
  }

  filtered.forEach(item => container.appendChild(buildItem(item)));
}

function buildItem(item) {
  const div = document.createElement("div");
  div.className = "rw-item";

  const sectionLabel = {
    summary:    "Summary",
    experience: "Experience",
    project:    "Projects",
  }[item.section] || item.section;

  const org   = item.organization ? ` @ ${esc(item.organization)}` : "";
  const label = esc(item.label || sectionLabel);

  let badge = "";
  if (item.recommend === "recommended") {
    badge = `<span class="badge badge-rec">Recommended</span>`;
  } else if (item.recommend === "optional") {
    badge = `<span class="badge badge-opt">Optional</span>`;
  }

  div.innerHTML = `
    <div class="rw-head">
      <label class="rw-label">
        <input type="checkbox" class="rw-check" data-idx="${item.index}"${approvedSet.has(item.index) ? " checked" : ""}>
        <span class="section-chip">${esc(sectionLabel)}</span>
        <span class="item-label">${label}${org}</span>
      </label>
      ${badge}
    </div>
    <div class="diff-label">Before</div>
    <div class="rw-before">${esc(item.before)}</div>
    <div class="diff-label" style="margin-top:5px">After</div>
    <div class="rw-after">${esc(item.after)}</div>
  `;

  div.querySelector(".rw-check").addEventListener("change", e => {
    if (e.target.checked) approvedSet.add(item.index);
    else approvedSet.delete(item.index);
  });

  return div;
}

// ── Tab counts ──
function updateCounts() {
  const counts = { all: allItems.length, summary: 0, experience: 0, project: 0 };
  for (const item of allItems) {
    if (item.section in counts) counts[item.section]++;
  }
  for (const [section, count] of Object.entries(counts)) {
    const el = document.getElementById(`cnt-${section}`);
    if (el) el.textContent = count ? ` (${count})` : "";
  }
}

function clearCounts() {
  ["all", "summary", "experience", "project"].forEach(s => {
    const el = document.getElementById(`cnt-${s}`);
    if (el) el.textContent = "";
  });
}

// ── Apply ──
async function applyApproved() {
  if (!approvedSet.size) {
    setStatus("No items selected — check at least one item to apply.");
    return;
  }

  const applyBtn = document.getElementById("apply-btn");
  applyBtn.disabled = true;
  applyBtn.textContent = "Applying…";

  try {
    const body = { approved_indices: [...approvedSet] };
    if (currentDiffSource) body.source_filename = currentDiffSource;

    const res  = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/apply`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) { data = null; }

    if (!res.ok) {
      setStatus("Error: " + (data?.detail || text.slice(0, 200) || res.status));
      return;
    }

    const n = data.applied;
    const m = data.mismatches?.length ?? 0;
    let applyMsg = `Applied ${n} rewrite${n !== 1 ? "s" : ""}.`;
    if (m) applyMsg += ` ${m} skipped — resume content changed since this diff was generated.`;
    setStatus(applyMsg + " Fetching updated resume…");

    // Fetch the new (after) HTML for the right pane
    try {
      const htmlRes = await fetch(`${BASE_URL}/variants/${variantId}/html`);
      if (htmlRes.ok) {
        const afterHtml = await htmlRes.text();
        const afterBlobUrl = URL.createObjectURL(new Blob([afterHtml], { type: "text/html" }));

        // Enter comparison mode: left = before, right = after
        enterComparisonMode(afterBlobUrl);
        let doneMsg = `Applied ${n} rewrite${n !== 1 ? "s" : ""}. Left: original · Right: updated.`;
        if (m) doneMsg += ` (${m} skipped — stale content)`;
        setStatus(doneMsg);
      }
    } catch (_) {
      setStatus(`Applied ${n} rewrite${n !== 1 ? "s" : ""}. Resume updated.`);
    }

    // Clear items — pending rewrites are consumed
    allItems    = [];
    approvedSet = new Set();
    document.getElementById("items-scroll").innerHTML = "";
    document.getElementById("footer-actions").classList.add("hidden");
    clearCounts();
  } catch (e) {
    setStatus("Error: " + e.message);
  } finally {
    applyBtn.disabled = false;
    applyBtn.textContent = "Apply Approved";
  }
}

// ── Comparison mode: left pane becomes "Before" resume, right becomes "After" ──
function enterComparisonMode(afterBlobUrl) {
  // Switch left pane: hide items UI, show before-frame
  document.getElementById("left-toolbar-review").classList.add("hidden");
  document.getElementById("left-toolbar-compare").classList.remove("hidden");
  document.getElementById("items-scroll").classList.add("hidden");
  document.getElementById("before-frame").classList.remove("hidden");
  document.getElementById("before-frame").src = beforeBlobUrl;

  // Right pane shows the after state
  document.getElementById("resume-frame").src = afterBlobUrl;
  document.getElementById("right-label").textContent = "After — rewrites applied";

  // Expand left pane to 50/50
  document.getElementById("main-content").classList.add("comparing");
}

function exitComparisonMode() {
  document.getElementById("left-toolbar-review").classList.remove("hidden");
  document.getElementById("left-toolbar-compare").classList.add("hidden");
  document.getElementById("items-scroll").classList.remove("hidden");
  document.getElementById("before-frame").classList.add("hidden");
  document.getElementById("main-content").classList.remove("comparing");
}

// ── Discard ──
async function discard() {
  const msg = currentDiffSource
    ? "Clear this diff from view? (The saved file is kept on disk.)"
    : "Discard pending rewrites?";
  if (!confirm(msg)) return;

  // Only delete the pending file when we're working from it, not from a historical diff
  if (currentDiffSource === null) {
    try {
      await fetch(`${BASE_URL}/variants/${variantId}/rewrite/pending`, { method: "DELETE" });
    } catch (_) {}
  }

  allItems          = [];
  approvedSet       = new Set();
  currentDiffSource = null;
  document.getElementById("history-select").value = "";
  document.getElementById("items-scroll").innerHTML = "";
  document.getElementById("footer-actions").classList.add("hidden");
  clearCounts();
  setStatus("Rewrites cleared.");
}

// ── Helpers ──
function setStatus(msg) {
  document.getElementById("status-bar").textContent = msg;
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Start ──
init();
