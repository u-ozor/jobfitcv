// chunk_review.js

const params    = new URLSearchParams(location.search);
const variantId = params.get("variant");

// ── State ──
let tierData          = null;  // raw API response
let workingSelected   = [];    // current working selection (chunks, may differ from tierData.selected)
let workingCandidates = [];    // remaining candidates
let originalSelIds    = new Set();
let dirty             = false;
let proposedSummary   = null;  // set after synthesis
let quotas            = {};    // {type: limit} from API
let viewMode          = "tier"; // "tier" | "category"
let draggedId         = null;
let disabledChunks    = [];    // active:false chunks from /wizard/chunks
let rewriteMap        = {};    // chunk_id → pending rewrite item
let rewriteDecisions  = {};    // chunk_id → "accepted"

// ── DOM ──
const statusBar       = document.getElementById("status-bar");
const pageTitle       = document.getElementById("page-title");
const applyBtn        = document.getElementById("apply-btn");
const previewBtn      = document.getElementById("preview-btn");
const assessBtn       = document.getElementById("assess-btn");
const rewriteRunBtn   = document.getElementById("rewrite-run-btn");
const synthBtn        = document.getElementById("synth-btn");
const resumeFrame     = document.getElementById("resume-frame");
const placeholder     = document.getElementById("resume-placeholder");
const synthModal      = document.getElementById("synth-modal");
const synthCurrent    = document.getElementById("synth-current");
const synthProposed   = document.getElementById("synth-proposed");
const jobPreviewInput = document.getElementById("job-preview-input");
const viewBtnTier     = document.getElementById("view-btn-tier");
const viewBtnCat      = document.getElementById("view-btn-cat");

// Theme is handled by theme-picker.js (loaded before this script).

document.getElementById("back-btn").addEventListener("click", () => window.close());

// ── View toggle ──
viewBtnTier.addEventListener("click", () => {
  if (viewMode === "tier") return;
  viewMode = "tier";
  viewBtnTier.classList.add("active");
  viewBtnCat.classList.remove("active");
  if (tierData) renderAll();
});
viewBtnCat.addEventListener("click", () => {
  if (viewMode === "category") return;
  viewMode = "category";
  viewBtnCat.classList.add("active");
  viewBtnTier.classList.remove("active");
  if (tierData) renderAll();
});

// ── Flag legend toggle ──
document.getElementById("flag-legend-toggle").addEventListener("click", function() {
  const body = document.getElementById("flag-legend-body");
  body.classList.toggle("open");
  this.textContent = body.classList.contains("open")
    ? "▾ What do the flags mean?"
    : "▶ What do the flags mean?";
});

// ── Tier collapse/expand ──
document.querySelectorAll(".tier-header").forEach(h => {
  h.addEventListener("click", () => {
    const tier = h.dataset.tier;
    const body = document.getElementById(`body-${tier}`);
    const chev = document.getElementById(`chev-${tier}`);
    body.classList.toggle("collapsed");
    chev.textContent = body.classList.contains("collapsed") ? "▸" : "▾";
  });
});


// =========================================================
// Init
// =========================================================

async function init() {
  if (!variantId) { setStatus("No variant specified."); return; }
  pageTitle.textContent = `${variantId} — Chunk Review`;
  setStatus("Loading…");
  try {
    const res  = await fetch(`${BASE_URL}/variants/${variantId}/chunk-review`);
    const data = await res.json();
    if (!res.ok) { setStatus("Error: " + (data.detail || res.status)); return; }
    tierData          = data.tiers;
    workingSelected   = [...tierData.selected];
    workingCandidates = [...tierData.candidates];
    originalSelIds    = new Set(tierData.selected.map(c => c.id));
    quotas            = data.quotas || {};
    const jdText = data.job_raw_text || data.job_preview || "";
    if (jdText) jobPreviewInput.value = jdText;

    const jdBtn = document.getElementById("jd-actual-btn");
    if (jdBtn && data.job_id) {
      jdBtn.href = `${BASE_URL}/jobs/${data.job_id}/jd-actual`;
      jdBtn.style.display = "inline-block";
    }

    // Default CV has no linked job — scores are priority-based, not similarity-based
    if (variantId === "default") {
      jobPreviewInput.placeholder = "No linked job — paste a job description here to assess how well these chunks match it. Leave blank to skip Assess.";
      pageTitle.textContent = "Default CV — Chunk Review";
    }

    // Load disabled chunks separately (they're filtered before scoring)
    try {
      const allRes = await fetch(`${BASE_URL}/wizard/chunks`);
      if (allRes.ok) {
        const allData = await allRes.json();
        disabledChunks = (allData.chunks || []).filter(c => c.active === false);
      }
    } catch (_) {}

    // Load pending rewrite diff (chunk_id-keyed, optional — silently skipped if none)
    try {
      const rwRes = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/pending`);
      if (rwRes.ok) {
        const rwData = await rwRes.json();
        rewriteMap = {};
        for (const item of (rwData.items || [])) {
          if (item.chunk_id) rewriteMap[item.chunk_id] = item;
        }
      }
    } catch (_) {}

    // Thin resume warning
    const expCount = tierData.selected.filter(c => c.chunk?.type === 'experience').length;
    const banner = document.getElementById('thin-resume-banner');
    if (banner) {
      const isThin = tierData.selected.length < 20 || expCount === 0;
      banner.classList.toggle('hidden', !isThin);
    }

    renderAll();
    renderQuotas();
    setStatus(`Loaded — ${tierData.selected.length} selected, ${tierData.candidates.length} candidates, ${tierData.dropped.length} dropped, ${disabledChunks.length} disabled.`);
  } catch (e) {
    setStatus("Error: " + e.message);
  }
}

init();


// =========================================================
// Render
// =========================================================

function renderQuotas() {
  const row = document.getElementById("quota-row");
  if (!row || !Object.keys(quotas).length) return;
  // count selected by type
  const counts = {};
  for (const c of workingSelected) {
    const t = c.chunk_type || c.type || "?";
    counts[t] = (counts[t] || 0) + 1;
  }
  row.innerHTML = Object.entries(quotas).map(([type, limit]) => {
    const used  = counts[type] || 0;
    const cls   = used >= limit ? "qfull" : "";
    return `<span class="quota-chip"><span class="qtype">${type}</span> <span class="${cls}">${used}/${limit}</span></span>`;
  }).join("");
}

function renderAll() {
  if (viewMode === "category") {
    document.querySelectorAll("#chunks-scroll .tier").forEach(t => t.style.display = "none");
    renderCategoryView();
  } else {
    document.querySelectorAll("#chunks-scroll .tier").forEach(t => t.style.display = "");
    document.querySelectorAll("#chunks-scroll .cat-type-block").forEach(b => b.remove());
    renderTier("selected",  workingSelected,  false);
    renderCandidates();
    renderTier("dropped",   tierData.dropped, true);
    renderDisabled();
    updateCounts();
  }
  renderQuotas();
}

function renderTier(name, chunks, dropped) {
  const body = document.getElementById(`body-${name}`);
  body.innerHTML = "";
  chunks.forEach((chunk, i) => {
    body.appendChild(buildCard(chunk, name, dropped, i + 1));
  });
}

function renderCandidates() {
  const body = document.getElementById("body-candidates");
  body.innerHTML = "";

  const quota     = workingCandidates.filter(c => c.cut_reason === "quota");
  const threshold = workingCandidates.filter(c => c.cut_reason === "threshold");
  const manual    = workingCandidates.filter(c => c.cut_reason === "manual");

  let counter = 1;
  if (manual.length)    counter = appendSubgroup(body, "Manually removed",        manual,     counter);
  if (quota.length)     counter = appendSubgroup(body, "Near miss — quota full",   quota,      counter);
  if (threshold.length)          appendSubgroup(body, "Near miss — below threshold", threshold, counter);
}

function appendSubgroup(parent, label, chunks, startNum) {
  const lbl = document.createElement("div");
  lbl.className = "subgroup-label";
  lbl.textContent = label;
  parent.appendChild(lbl);
  chunks.forEach((chunk, i) => parent.appendChild(buildCard(chunk, "candidates", false, startNum + i)));
  return startNum + chunks.length;
}

function updateCounts() {
  document.getElementById("cnt-selected").textContent   = ` (${workingSelected.length})`;
  document.getElementById("cnt-candidates").textContent = ` (${workingCandidates.length})`;
  document.getElementById("cnt-dropped").textContent    = ` (${tierData.dropped.length})`;
  document.getElementById("cnt-disabled").textContent   = ` (${disabledChunks.length})`;
}

function renderDisabled() {
  const body = document.getElementById("body-disabled");
  body.innerHTML = "";
  disabledChunks.forEach((chunk, i) => {
    body.appendChild(buildDisabledCard(chunk, i + 1));
  });
}

function buildDisabledCard(chunk, num) {
  const div = document.createElement("div");
  div.className = "chunk-card disabled-card";
  div.dataset.id = chunk.id;
  div.innerHTML = `
    <div class="card-header" style="cursor:default">
      <span class="card-num">${num}</span>
      <div class="card-header-main">
        <div class="card-title-row">
          <span class="card-title">${esc(chunk.title || chunk.id)}</span>
        </div>
        <div class="card-meta-row">
          <span class="card-toggle toggle-off">○ disabled</span>
          <span class="card-type">${esc(chunk.type || "")}</span>
          <span class="card-id">${esc(chunk.id)}</span>
          <a class="card-wizard-link" href="http://localhost:8000/wizard?edit=${esc(chunk.id)}" target="_blank" title="Edit in Wizard">↗ edit</a>
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-content">${esc(chunk.content || "")}</div>
    </div>
  `;
  return div;
}


// =========================================================
// Category view
// =========================================================

function renderCategoryView() {
  const scroll = document.getElementById("chunks-scroll");

  // Preserve collapse state of existing category blocks before rebuilding
  const collapseState = {};
  scroll.querySelectorAll(".cat-type-block").forEach(b => {
    const name = b.querySelector(".cat-type-name")?.textContent;
    const body = b.querySelector(".cat-type-body");
    if (name && body) collapseState[name] = body.classList.contains("collapsed");
  });

  scroll.querySelectorAll(".cat-type-block").forEach(b => b.remove());

  const allChunks = [
    ...workingSelected.map(c => ({ ...c, _tier: "selected" })),
    ...workingCandidates.map(c => ({ ...c, _tier: "candidates" })),
    ...tierData.dropped.map(c => ({ ...c, _tier: "dropped" })),
    ...disabledChunks.map(c => ({ ...c, _tier: "disabled" })),
  ];

  const byType = {};
  for (const c of allChunks) {
    const t = c.type || "?";
    if (!byType[t]) byType[t] = [];
    byType[t].push(c);
  }

  const typeOrder = ["summary", "experience", "project", "skill", "education", "certification"];
  const sortedTypes = [
    ...typeOrder.filter(t => byType[t]),
    ...Object.keys(byType).filter(t => !typeOrder.includes(t)),
  ];

  for (const type of sortedTypes) {
    const chunks    = byType[type];
    const selChunks = chunks.filter(c => c._tier === "selected");
    const manual    = chunks.filter(c => c._tier === "candidates" && c.cut_reason === "manual");
    const quota     = chunks.filter(c => c._tier === "candidates" && c.cut_reason === "quota");
    const threshold = chunks.filter(c => c._tier === "candidates" && c.cut_reason === "threshold");
    const dropped   = chunks.filter(c => c._tier === "dropped");
    const disabled  = chunks.filter(c => c._tier === "disabled");

    const block = document.createElement("div");
    block.className = "cat-type-block";

    const limit = quotas[type] != null ? quotas[type] : "?";
    const chips = [];
    if (selChunks.length) chips.push(`<span class="cat-chip cat-chip-sel">${selChunks.length}/${limit} sel</span>`);
    if (quota.length)     chips.push(`<span class="cat-chip cat-chip-quot">${quota.length} quota cut</span>`);
    if (threshold.length) chips.push(`<span class="cat-chip cat-chip-thr">${threshold.length} below thr</span>`);
    if (manual.length)    chips.push(`<span class="cat-chip cat-chip-thr">${manual.length} removed</span>`);

    const hdr = document.createElement("div");
    hdr.className = "cat-type-header";
    hdr.innerHTML = `
      <span class="cat-chev">▾</span>
      <span class="cat-type-name">${type}</span>
      <div class="cat-type-chips">${chips.join("")}</div>
    `;

    const body = document.createElement("div");
    body.className = "cat-type-body";

    hdr.addEventListener("click", () => {
      body.classList.toggle("collapsed");
      hdr.querySelector(".cat-chev").textContent = body.classList.contains("collapsed") ? "▸" : "▾";
    });

    let counter = 1;
    if (selChunks.length) counter = appendCatSubgroup(body, "Selected",                   selChunks,  counter, false);
    if (manual.length)    counter = appendCatSubgroup(body, "Manually removed",            manual,     counter, false);
    if (quota.length)     counter = appendCatSubgroup(body, "Near miss — quota full",      quota,      counter, false);
    if (threshold.length) counter = appendCatSubgroup(body, "Near miss — below threshold", threshold,  counter, false);
    if (dropped.length)   counter = appendCatSubgroup(body, "Dropped",                    dropped,    counter, true);
    if (disabled.length)  appendCatDisabled(body, disabled, counter);

    // Restore previous collapse state; default open for first render
    if (collapseState[type] === true) {
      body.classList.add("collapsed");
      hdr.querySelector(".cat-chev").textContent = "▸";
    }

    block.appendChild(hdr);
    block.appendChild(body);
    scroll.appendChild(block);
  }
}

function appendCatDisabled(parent, chunks, startNum) {
  const subHdr  = document.createElement("div");
  subHdr.className = "cat-sub-header cat-sub-header-disabled";
  const subBody = document.createElement("div");
  subBody.className = "cat-sub-body collapsed";

  subHdr.innerHTML = `<span class="cat-sub-chev">▸</span><span class="cat-sub-label">Disabled</span>`;
  subHdr.addEventListener("click", () => {
    subBody.classList.toggle("collapsed");
    subHdr.querySelector(".cat-sub-chev").textContent = subBody.classList.contains("collapsed") ? "▸" : "▾";
  });

  chunks.forEach((chunk, i) => subBody.appendChild(buildDisabledCard(chunk, startNum + i)));

  parent.appendChild(subHdr);
  parent.appendChild(subBody);
}

function appendCatSubgroup(parent, label, chunks, startNum, dropped) {
  const subHdr  = document.createElement("div");
  subHdr.className = "cat-sub-header";
  const subBody = document.createElement("div");
  subBody.className = "cat-sub-body";

  subHdr.innerHTML = `<span class="cat-sub-chev">▾</span><span class="cat-sub-label">${label}</span>`;
  subHdr.addEventListener("click", () => {
    subBody.classList.toggle("collapsed");
    subHdr.querySelector(".cat-sub-chev").textContent = subBody.classList.contains("collapsed") ? "▸" : "▾";
  });

  chunks.forEach((chunk, i) => {
    subBody.appendChild(buildCard(chunk, chunk._tier, dropped, startNum + i));
  });

  parent.appendChild(subHdr);
  parent.appendChild(subBody);
  return startNum + chunks.length;
}


// =========================================================
// Card builder
// =========================================================

const isWarm = () => document.body.dataset.theme === "warm";

function simColor(sim) {
  if (isWarm()) return sim >= 0.70 ? "#0b766c" : sim >= 0.56 ? "#b45309" : "#be1239";
  return sim >= 0.70 ? "#2dd4bf" : sim >= 0.56 ? "#fbbf24" : "#fb7185";
}
function kwColor(kw) {
  const m = kw * 8;
  if (isWarm()) return m >= 5 ? "#0b766c" : m >= 2 ? "#b45309" : "#be1239";
  return m >= 5 ? "#2dd4bf" : m >= 2 ? "#fbbf24" : "#fb7185";
}

function buildRewritePanel(chunk) {
  const item = rewriteMap[chunk.id];
  if (!item) return "";

  const isAccepted = rewriteDecisions[chunk.id] === "accepted";
  const isStale    = item.before && item.before !== chunk.content;

  const badgeClass = isAccepted ? "accepted" : isStale ? "stale" : "";
  const badgeText  = isAccepted ? "↻ rewrite accepted" : isStale ? "↻ rewrite (stale)" : "↻ rewrite available";

  return `
    <div class="rw-panel">
      <div class="rw-header">
        <span class="rw-badge ${badgeClass}">${badgeText}</span>
        <span class="rw-chev">▸</span>
      </div>
      <div class="rw-body hidden">
        ${isStale ? `<div class="rw-label" style="color:var(--rose)">Chunk was edited after rewrite — re-run Rewrite to refresh</div>` : `
        <div class="rw-label">Before</div>
        <div class="rw-before">${esc(item.before)}</div>
        <div class="rw-label">After</div>
        <div class="rw-after">${esc(item.after)}</div>
        <div class="rw-actions">
          <button class="rw-accept-btn">${isAccepted ? "✓ Accepted" : "Accept"}</button>
          ${isAccepted ? `<button class="rw-reject-btn">Undo</button>` : ""}
        </div>`}
      </div>
    </div>`;
}

function buildCard(chunk, tier, dropped, num) {
  const div = document.createElement("div");
  div.className = `chunk-card ${tier}-card`;
  div.dataset.id = chunk.id;

  const isSelected = tier === "selected";
  const kwMatches  = Math.round(chunk.keyword_score * 8);
  const priVal     = Math.round(chunk.priority_score * 10);

  const flagHtml   = buildFlags(chunk, tier);
  const dragHandle = isSelected ? `<span class="card-drag">⠿</span>` : "";
  const rwPanel    = isSelected ? buildRewritePanel(chunk) : "";

  div.innerHTML = `
    <div class="card-header">
      ${dragHandle}
      <span class="card-num">${num ?? ""}</span>
      <div class="card-header-main">
        <div class="card-title-row">
          <span class="card-title">${esc(chunk.title || chunk.id)}</span>
        </div>
        <div class="card-meta-row">
          <span class="card-toggle ${isSelected ? "toggle-on" : "toggle-off"}">
            ${isSelected ? "✓ in" : "○ out"}
          </span>
          <span class="card-type">${esc(chunk.type)}</span>
          <span class="card-id">${esc(chunk.id)}</span>
          <a class="card-wizard-link" href="http://localhost:8000/wizard?edit=${esc(chunk.id)}" target="_blank" title="Edit in Wizard">↗ edit</a>
        </div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-content">${esc(chunk.content || "")}</div>
      <div class="score-bar-wrap">
        <div class="score-bar">
          <div class="seg seg-sim">
            <div class="seg-fill" style="width:${chunk.similarity*100}%;background:${simColor(chunk.similarity)}"></div>
            <div class="seg-empty"></div>
          </div>
          <div class="seg seg-kw">
            <div class="seg-fill" style="width:${chunk.keyword_score*100}%;background:${kwColor(chunk.keyword_score)}"></div>
            <div class="seg-empty"></div>
          </div>
          <div class="seg seg-pri">
            <div class="seg-fill" style="width:${chunk.priority_score*100}%;background:#94a3b8"></div>
            <div class="seg-empty"></div>
          </div>
        </div>
        <div class="score-vals">
          <span><span class="score-val-label">sim </span>${chunk.similarity.toFixed(2)}</span>
          <span><span class="score-val-label">kw </span>${kwMatches}</span>
          <span><span class="score-val-label">p</span>${priVal}</span>
          <span><span class="score-val-label">total </span>${chunk.score.toFixed(3)}</span>
        </div>
      </div>
      ${flagHtml}
      <div id="assmt-wrap-${esc(chunk.id)}">${chunk.ollama_assessment ? buildAssessment(chunk.ollama_assessment) : ""}</div>
      ${rwPanel}
    </div>
  `;

  if (!dropped) {
    div.querySelector(".card-header").addEventListener("click", e => {
      if (e.target.closest(".card-drag"))        return;
      if (e.target.closest(".card-wizard-link")) return;
      toggleChunk(chunk.id);
    });
  }

  // Rewrite panel toggle + accept/reject
  const rwHeader = div.querySelector(".rw-header");
  if (rwHeader) {
    rwHeader.addEventListener("click", e => {
      e.stopPropagation();
      const body = div.querySelector(".rw-body");
      const chev = div.querySelector(".rw-chev");
      if (body) body.classList.toggle("hidden");
      if (chev) chev.textContent = body?.classList.contains("hidden") ? "▸" : "▾";
    });
    div.querySelector(".rw-accept-btn")?.addEventListener("click", e => {
      e.stopPropagation();
      rewriteDecisions[chunk.id] = "accepted";
      dirty = true;
      applyBtn.disabled = false;
      renderAll();
    });
    div.querySelector(".rw-reject-btn")?.addEventListener("click", e => {
      e.stopPropagation();
      delete rewriteDecisions[chunk.id];
      dirty = true;
      renderAll();
    });
  }

  if (isSelected) {
    div.setAttribute("draggable", "true");

    div.addEventListener("dragstart", e => {
      draggedId = chunk.id;
      // Brief delay so the drag ghost renders before opacity drops
      requestAnimationFrame(() => div.classList.add("dragging"));
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", chunk.id);
    });

    div.addEventListener("dragend", () => {
      div.classList.remove("dragging");
      draggedId = null;
      document.querySelectorAll(".drag-over").forEach(el => el.classList.remove("drag-over"));
    });

    div.addEventListener("dragover", e => {
      if (!draggedId || draggedId === chunk.id) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".drag-over").forEach(el => el.classList.remove("drag-over"));
      div.classList.add("drag-over");
    });

    div.addEventListener("dragleave", e => {
      if (!div.contains(e.relatedTarget)) {
        div.classList.remove("drag-over");
      }
    });

    div.addEventListener("drop", e => {
      e.preventDefault();
      div.classList.remove("drag-over");
      if (!draggedId || draggedId === chunk.id) return;

      const fromIdx = workingSelected.findIndex(c => c.id === draggedId);
      const toIdx   = workingSelected.findIndex(c => c.id === chunk.id);
      if (fromIdx < 0 || toIdx < 0) return;

      const [moved] = workingSelected.splice(fromIdx, 1);
      workingSelected.splice(toIdx, 0, moved);

      dirty = true;
      applyBtn.disabled = false;

      renderAll();
    });
  }

  return div;
}

function buildFlags(chunk, tier) {
  const flags = chunk.flags || [];
  const parts = [];

  for (const f of flags) {
    if (f === "strong_signal")       parts.push(`<span class="flag flag-good">✓ strong signal</span>`);
    else if (f === "marginal_fit")   parts.push(`<span class="flag flag-bad">⚠ marginal fit</span>`);
    else if (f === "no_keyword_overlap")  parts.push(`<span class="flag flag-bad">⚠ no keyword overlap</span>`);
    else if (f === "low_keyword_overlap") parts.push(`<span class="flag flag-warn">⚠ low keyword overlap</span>`);
    else if (f === "priority_carried")    parts.push(`<span class="flag flag-warn">⚠ priority carried</span>`);
  }

  if (tier === "candidates" || tier === "dropped") {
    if (chunk.cut_reason === "quota")     parts.push(`<span class="flag flag-cut">cut — quota full</span>`);
    if (chunk.cut_reason === "threshold") parts.push(`<span class="flag flag-cut">cut — below threshold</span>`);
    if (chunk.cut_reason === "manual")    parts.push(`<span class="flag flag-cut">removed manually</span>`);
  }

  if (!parts.length) return "";
  return `<div class="flags-row">${parts.join("")}</div>`;
}

function buildAssessment(text) {
  if (!text) return "";
  const cls = text.startsWith("Relevant:") ? "assessment-relevant" : "assessment-weak";
  return `<div class="assessment-line ${cls}">${esc(text)}</div>`;
}

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


// =========================================================
// Toggle chunk
// =========================================================

function toggleChunk(chunkId) {
  const selIdx = workingSelected.findIndex(c => c.id === chunkId);
  if (selIdx >= 0) {
    // Move selected → candidates (manual removal)
    const chunk = workingSelected.splice(selIdx, 1)[0];
    chunk.cut_reason = "manual";
    workingCandidates.unshift(chunk);
  } else {
    const canIdx = workingCandidates.findIndex(c => c.id === chunkId);
    if (canIdx < 0) return;
    // Move candidates → selected
    const chunk = workingCandidates.splice(canIdx, 1)[0];
    chunk.cut_reason = null;
    workingSelected.push(chunk);
  }

  // Check if dirty vs original
  const currentIds = new Set(workingSelected.map(c => c.id));
  dirty = (
    currentIds.size !== originalSelIds.size ||
    [...currentIds].some(id => !originalSelIds.has(id))
  );
  applyBtn.disabled = !dirty;

  renderAll();
}


// =========================================================
// Rewrite
// =========================================================

rewriteRunBtn.addEventListener("click", async () => {
  if (!tierData) return;
  if (variantId === "default") { setStatus("Rewrite not available for the default CV."); return; }
  setStatus("Running rewrite — this takes ~30 seconds…");
  rewriteRunBtn.disabled = true;
  rewriteRunBtn.textContent = "Rewriting…";
  try {
    const res  = await fetch(`${BASE_URL}/variants/${variantId}/rewrite/preview`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) { setStatus("Rewrite error: " + (data.detail || res.status)); return; }

    rewriteMap = {};
    for (const item of (data.items || [])) {
      if (item.chunk_id) rewriteMap[item.chunk_id] = item;
    }
    rewriteDecisions = {};
    renderAll();
    const n = Object.keys(rewriteMap).length;
    setStatus(`Rewrite complete — ${n} suggestion${n !== 1 ? "s" : ""} available. Expand cards to review.`);
  } catch (e) {
    setStatus("Rewrite error: " + e.message);
  } finally {
    rewriteRunBtn.disabled = false;
    rewriteRunBtn.textContent = "Rewrite";
  }
});


// Preview
// =========================================================

previewBtn.addEventListener("click", async () => {
  if (!tierData) return;
  setStatus("Rendering preview…");
  previewBtn.disabled = true;

  try {
    const ids = workingSelected.map(c => c.id);
    const res = await fetch(`${BASE_URL}/variants/${variantId}/chunk-review/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chunk_ids: ids })
    });
    const data = await res.json();
    if (!res.ok) { setStatus("Preview error: " + (data.detail || res.status)); return; }

    resumeFrame.srcdoc = data.html;
    resumeFrame.classList.remove("hidden");
    placeholder.classList.add("hidden");
    document.getElementById("right-label").textContent = "Preview — current selection";
    setStatus("Preview loaded.");
  } catch (e) {
    setStatus("Preview error: " + e.message);
  } finally {
    previewBtn.disabled = false;
  }
});


// =========================================================
// Assess Fit (Ollama)
// =========================================================

assessBtn.addEventListener("click", async () => {
  if (!tierData) return;
  assessBtn.disabled = true;
  setStatus("Running Ollama assessment…");

  const ids = [
    ...workingSelected.map(c => c.id),
    ...workingCandidates.map(c => c.id)
  ];

  const jobPreviewOverride = jobPreviewInput.value.trim() || null;

  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/chunk-review/assess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chunk_ids: ids, job_preview_override: jobPreviewOverride })
    });
    const data = await res.json();
    if (!res.ok) { setStatus("Assess error: " + (data.detail || res.status)); return; }

    // Patch assessment cache into working state and update DOM
    const all = [...workingSelected, ...workingCandidates, ...tierData.dropped];
    for (const chunk of all) {
      if (data.assessments[chunk.id]) {
        chunk.ollama_assessment = data.assessments[chunk.id];
        const wrap = document.getElementById(`assmt-wrap-${chunk.id}`);
        if (wrap) wrap.innerHTML = buildAssessment(chunk.ollama_assessment);
      }
    }

    const count = Object.keys(data.assessments).length;
    setStatus(`Assessment complete — ${count} chunks evaluated.`);
  } catch (e) {
    setStatus("Assess error: " + e.message);
  } finally {
    assessBtn.disabled = false;
  }
});


// =========================================================
// Synthesize Summary (provider-agnostic — SUMMARY_SYNTH_PROVIDER/MODEL)
// =========================================================

synthBtn.addEventListener("click", async () => {
  if (!tierData) return;
  synthBtn.disabled = true;
  setStatus("Synthesizing summary…");

  const ids = workingSelected.map(c => c.id);

  try {
    const res = await fetch(`${BASE_URL}/variants/${variantId}/summary/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chunk_ids: ids })
    });
    const data = await res.json();
    if (!res.ok) { setStatus("Synthesize error: " + (data.detail || res.status)); return; }

    proposedSummary = data.proposed;
    synthCurrent.textContent  = data.current || "(no current summary)";
    synthProposed.textContent = data.proposed;
    synthModal.classList.remove("hidden");
    setStatus("Synthesis ready — review and approve or discard.");
  } catch (e) {
    setStatus("Synthesize error: " + e.message);
  } finally {
    synthBtn.disabled = false;
  }
});

document.getElementById("synth-discard-btn").addEventListener("click", () => {
  synthModal.classList.add("hidden");
  proposedSummary = null;
  setStatus("Summary discarded.");
});

document.getElementById("synth-approve-btn").addEventListener("click", async () => {
  synthModal.classList.add("hidden");
  await applySelection(proposedSummary);
  proposedSummary = null;
});


// =========================================================
// Apply Selection
// =========================================================

applyBtn.addEventListener("click", () => applySelection(null));

async function applySelection(summaryOverride) {
  if (!tierData) return;
  applyBtn.disabled = true;
  setStatus("Applying selection…");

  const ids  = workingSelected.map(c => c.id);
  const body = { chunk_ids: ids };
  if (summaryOverride) body.summary_override = summaryOverride;

  const accepted = Object.entries(rewriteDecisions)
    .filter(([, v]) => v === "accepted")
    .reduce((acc, [cid]) => {
      const item = rewriteMap[cid];
      if (item) acc[cid] = item.after;
      return acc;
    }, {});
  if (Object.keys(accepted).length) body.rewrite_overrides = accepted;

  try {
    let res = await fetch(`${BASE_URL}/variants/${variantId}/chunk-review/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    let data = await res.json();

    if (res.status === 409 && (data.detail || "").includes("general-purpose CV")) {
      const proceed = confirm(
        `${data.detail}\n\nThis is a general-purpose CV, not tied to one job posting — applying will change it for every job using it. Continue?`
      );
      if (!proceed) { setStatus("Apply cancelled."); applyBtn.disabled = false; return; }
      body.confirm_protected = true;
      res = await fetch(`${BASE_URL}/variants/${variantId}/chunk-review/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      data = await res.json();
    }

    if (!res.ok) { setStatus("Apply error: " + (data.detail || res.status)); applyBtn.disabled = false; return; }

    // Reset dirty state
    originalSelIds   = new Set(workingSelected.map(c => c.id));
    dirty            = false;
    rewriteDecisions = {};
    rewriteMap       = {};
    applyBtn.disabled = true;

    setStatus(`Applied — ${ids.length} chunks committed. Refreshing preview…`);

    // Auto-preview the new output
    const htmlRes = await fetch(`${BASE_URL}/variants/${variantId}/html`);
    if (htmlRes.ok) {
      const html = await htmlRes.text();
      resumeFrame.srcdoc = html;
      resumeFrame.classList.remove("hidden");
      placeholder.classList.add("hidden");
      document.getElementById("right-label").textContent = "Applied — live output";
    }
  } catch (e) {
    setStatus("Apply error: " + e.message);
    applyBtn.disabled = false;
  }
}


// =========================================================
// Status
// =========================================================

function setStatus(msg) {
  statusBar.textContent = msg;
}

// ── Job context shrink toggle ──────────────────────────────
const contextShrinkBtn  = document.getElementById('context-shrink-btn');
const contextCollapsible = document.getElementById('context-collapsible');
if (contextShrinkBtn && contextCollapsible) {
  contextShrinkBtn.addEventListener('click', () => {
    const hidden = contextCollapsible.style.display === 'none';
    contextCollapsible.style.display = hidden ? '' : 'none';
    contextShrinkBtn.textContent = hidden ? '▾' : '▸';
  });
}
