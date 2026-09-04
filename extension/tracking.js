// tracking.js

const APP_STATUSES = ["", "Applied", "Screening", "Interviewing", "Offer", "Rejected", "Withdrawn", "Archived", "Parked"];
const HOT_STATUSES = ["Rejected", "Withdrawn", "Archived"];
const CATEGORIES   = ["Main", "PT", "Bridge", "Other"];

let cachedJobs         = [];
let cachedVariantByJob = {};
let allRowPairs        = [];
const collapsedWeeks   = new Set(); // week_label keys that are collapsed (session-only)

// ─── Week grouping ────────────────────────────────────────────────────────────

function weekDisplay(mondayStr) {
  if (!mondayStr || mondayStr === "unknown") return "Unknown Week";
  // Parse as local noon to avoid DST boundary issues
  const mon = new Date(mondayStr + "T12:00:00");
  const sun = new Date(mon);
  sun.setDate(sun.getDate() + 6);
  const fmt = d => d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  return `${fmt(mon)} – ${fmt(sun)}`;
}

function buildWeekGroups(jobs) {
  const groups = {};
  for (const job of jobs) {
    if (!job.company || job.company === "—") continue;
    const key = job.week_label || "unknown";
    (groups[key] = groups[key] || []).push(job);
  }
  // Most recent week first
  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([key, jobs]) => ({ key, label: weekDisplay(key), jobs }));
}

function toggleWeek(key) {
  collapsedWeeks.has(key) ? collapsedWeeks.delete(key) : collapsedWeeks.add(key);
  render();
}

// ─── Load ─────────────────────────────────────────────────────────────────────

async function load() {
  const [jobsRes, variantsRes] = await Promise.all([
    fetch(`${BASE_URL}/jobs/`),
    fetch(`${BASE_URL}/variants/`)
  ]);
  cachedJobs = await jobsRes.json();
  const variants = await variantsRes.json();
  cachedVariantByJob = {};
  for (const v of variants) cachedVariantByJob[v.job_id] = v;

  render();
  initSearch();
}

// ─── Render ───────────────────────────────────────────────────────────────────

function render() {
  const tbody = document.getElementById("jobs-tbody");
  if (!cachedJobs.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">No jobs captured yet.</td></tr>';
    return;
  }

  const defaults    = cachedJobs.filter(j => !j.company || j.company === "—");
  const weekGroups  = buildWeekGroups(cachedJobs);

  tbody.innerHTML = "";
  allRowPairs = [];

  // Fixed "Default CVs" section
  if (defaults.length) {
    tbody.appendChild(makeSectionHeader("Default CVs", null));
    for (const job of defaults) {
      const pair = buildRowPair(job, cachedVariantByJob[job.job_id], "Default CVs");
      allRowPairs.push(pair);
      tbody.appendChild(pair.jobRow);
      tbody.appendChild(pair.detailRow);
    }
  }

  // Week sections — derived entirely from DB week_label
  for (const group of weekGroups) {
    const isCollapsed = collapsedWeeks.has(group.key);
    tbody.appendChild(makeSectionHeader(group.label, group.key, group.jobs.length));

    let batchNum = 0;
    for (const job of group.jobs) {
      const pair = buildRowPair(job, cachedVariantByJob[job.job_id], group.label, ++batchNum);
      allRowPairs.push(pair);
      if (isCollapsed) {
        pair.jobRow.classList.add("batch-collapsed");
        pair.detailRow.classList.add("batch-collapsed");
      }
      tbody.appendChild(pair.jobRow);
      tbody.appendChild(pair.detailRow);
    }
  }

  const q = document.getElementById("tracking-search")?.value;
  if (q) filterRows(q);
}

function makeSectionHeader(label, weekKey, count) {
  const row = document.createElement("tr");
  row.className = "batch-header-row";
  if (weekKey) row.dataset.weekKey = weekKey;

  const isWeek      = !!weekKey;
  const isCollapsed = isWeek && collapsedWeeks.has(weekKey);
  const arrow       = isWeek ? `<span class="batch-arrow">${isCollapsed ? "▸" : "▾"}</span>` : "";
  const countBadge  = count != null ? `<span class="batch-count">${count}</span>` : "";

  row.innerHTML = `<td colspan="6">
    <div class="batch-header-inner">${arrow}<span class="batch-label">${esc(label)}</span>${countBadge}</div>
  </td>`;

  if (isWeek) {
    row.querySelector(".batch-arrow").addEventListener("click", e => { e.stopPropagation(); toggleWeek(weekKey); });
    row.querySelector(".batch-label").addEventListener("click", () => toggleWeek(weekKey));
  }

  return row;
}

// ─── Search ───────────────────────────────────────────────────────────────────

function initSearch() {
  const input    = document.getElementById("tracking-search");
  const clearBtn = document.getElementById("tracking-search-clear");
  if (!input) return;
  input.addEventListener("input", () => {
    filterRows(input.value);
    clearBtn.style.display = input.value ? "" : "none";
  });
  clearBtn.addEventListener("click", () => {
    input.value = "";
    clearBtn.style.display = "none";
    filterRows("");
  });
}

function filterRows(query) {
  const q = query.trim().toLowerCase();
  const weekHeaderRows = document.querySelectorAll("tr.batch-header-row");
  const weekVisible = new Map();
  weekHeaderRows.forEach(r => weekVisible.set(r, false));

  for (const { jobRow, detailRow, job, batchName } of allRowPairs) {
    const haystack = [job.title, job.company, job.track, job.focus, job.app_status, job.job_category, batchName]
      .filter(Boolean).join(" ").toLowerCase();
    const match = !q || haystack.includes(q);

    jobRow.classList.toggle("filter-hidden", !match);
    detailRow.classList.toggle("filter-hidden", !match);

    const weekKey    = getWeekKeyForRow(jobRow);
    const isCollapsed = weekKey && collapsedWeeks.has(weekKey);
    if (q && match) {
      jobRow.classList.remove("batch-collapsed");
    } else if (!q && isCollapsed) {
      jobRow.classList.add("batch-collapsed");
      detailRow.classList.add("batch-collapsed");
    } else if (!q && !isCollapsed) {
      jobRow.classList.remove("batch-collapsed");
    }

    if (match) {
      let prev = jobRow.previousElementSibling;
      while (prev) {
        if (prev.classList.contains("batch-header-row")) { weekVisible.set(prev, true); break; }
        prev = prev.previousElementSibling;
      }
    }
  }

  weekHeaderRows.forEach(r => r.classList.toggle("filter-hidden", !q ? false : !weekVisible.get(r)));
}

function getWeekKeyForRow(jobRow) {
  let prev = jobRow.previousElementSibling;
  while (prev) {
    if (prev.classList.contains("batch-header-row")) return prev.dataset.weekKey || null;
    prev = prev.previousElementSibling;
  }
  return null;
}

// ─── Row builder ──────────────────────────────────────────────────────────────

function verdictChip(assessment) {
  if (!assessment) return '<span class="verdict-chip pending">pending</span>';
  const word = assessment.trim().split(/\s+/)[0].toLowerCase().replace(/[^a-z]/g, "");
  const cls  = word === "submit" ? "submit" : word === "caveat" ? "caveat" : word === "skip" ? "skip" : "pending";
  return `<span class="verdict-chip ${cls}">${cls === "pending" ? "pending" : word}</span>`;
}

const CAT_COLORS = { Main: "#16a34a", PT: "#8b5cf6", Bridge: "#3b82f6", Other: "#6b7280" };

function buildRowPair(job, variant, batchName, num = "") {
  const jobRow = document.createElement("tr");
  jobRow.className = "job-row";
  jobRow.id = `row-${job.job_id}`;

  const outputBadge = variant
    ? `<div class="output-btns">
        <a href="${BASE_URL}/variants/${variant.id}/html" target="_blank">cv</a>
        <a href="${BASE_URL}/jobs/${esc(job.job_id)}/cover_letter/combined_pdf" target="_blank" class="merged">cv+cl</a>
       </div>`
    : `<span class="badge pending">${esc(job.status || "ingested")}</span>`;

  const date       = job.ingested_at ? new Date(job.ingested_at).toLocaleDateString() : "";
  const statusOpts = APP_STATUSES.map(s =>
    `<option value="${s}"${job.app_status === s ? " selected" : ""}>${s || "—"}</option>`
  ).join("");

  const cat      = job.job_category || "Main";
  const catColor = CAT_COLORS[cat] || CAT_COLORS["Main"];
  const catBadge = `<span class="cat-badge" style="background:${catColor}">${esc(cat)}</span>`;

  jobRow.innerHTML = `
    <td>${num ? '<span class="row-num">' + num + '</span>' : ''}<span class="expand-arrow">▶</span></td>
    <td>
      <div class="job-title">${esc(job.title || "Untitled")}${catBadge}${job.url ? `<a class="job-src-link" href="${job.url}" target="_blank" title="Open job posting" onclick="event.stopPropagation()">↗</a>` : ""}</div>
      ${job.company ? `<div class="job-company">${esc(job.company)}</div>` : ""}
    </td>
    <td><span class="track-chip">${esc(job.track || "—")}</span></td>
    <td>${outputBadge}</td>
    <td><select class="status-sel">${statusOpts}</select></td>
    <td class="date-cell">${date}</td>
  `;

  const detailRow = document.createElement("tr");
  detailRow.className = "detail-row hidden";
  detailRow.id = `detail-${job.job_id}`;

  const assessText = job.figurative_assessment || "";
  const notesText  = job.notes || "";
  const isHot      = HOT_STATUSES.includes(job.app_status);

  detailRow.innerHTML = `
    <td colspan="6">
      <div class="detail-inner">
        <div class="notes-panel">
          <div class="notes-label">notes</div>
          <textarea class="notes-input" placeholder="notes…" rows="3">${esc(notesText)}</textarea>
          <div class="notes-actions">
            <select class="status-sel-detail">${statusOpts}</select>
            <select class="cat-sel-detail" title="Job category">${CATEGORIES.map(c => `<option value="${c}"${(job.job_category || "Main") === c ? " selected" : ""}>${c}</option>`).join("")}</select>
            <button class="del-btn${isHot ? " hot" : ""}">Delete</button>
          </div>
        </div>
        <div class="assessment-panel">
          <div class="assessment-label">assessment ${verdictChip(assessText)}</div>
          <textarea class="assess-input" placeholder="Submit / Caveat / Skip — one line verdict…" rows="4">${esc(assessText)}</textarea>
        </div>
      </div>
    </td>
  `;

  // Expand toggle
  jobRow.addEventListener("click", e => {
    if (e.target.closest("select,a,button,.drag-handle")) return;
    const isExpanded = jobRow.classList.toggle("expanded");
    detailRow.classList.toggle("hidden", !isExpanded);
    if (isExpanded) {
      autoResize(detailRow.querySelector(".assess-input"));
      autoResize(detailRow.querySelector(".notes-input"));
    }
  });

  // Status sync
  const mainSel   = jobRow.querySelector(".status-sel");
  const detailSel = detailRow.querySelector(".status-sel-detail");
  function syncAndPatch(val) {
    mainSel.value = val; detailSel.value = val;
    patchJob(job.job_id, { app_status: val });
    const delBtn = detailRow.querySelector(".del-btn");
    HOT_STATUSES.includes(val) ? delBtn.classList.add("hot") : delBtn.classList.remove("hot");
  }
  mainSel.addEventListener("change",   e => syncAndPatch(e.target.value));
  detailSel.addEventListener("change", e => syncAndPatch(e.target.value));

  // Category select
  const catSel = detailRow.querySelector(".cat-sel-detail");
  catSel.addEventListener("change", () => patchJob(job.job_id, { job_category: catSel.value }));

  // Assess textarea
  const assessEl = detailRow.querySelector(".assess-input");
  assessEl.addEventListener("input", () => {
    autoResize(assessEl);
    detailRow.querySelector(".assessment-label").innerHTML = `assessment ${verdictChip(assessEl.value)}`;
  });
  assessEl.addEventListener("blur", () => patchJob(job.job_id, { figurative_assessment: assessEl.value }));

  // Notes textarea
  const notesEl = detailRow.querySelector(".notes-input");
  notesEl.addEventListener("input",  () => autoResize(notesEl));
  notesEl.addEventListener("blur",   () => patchJob(job.job_id, { notes: notesEl.value }));

  // Delete
  detailRow.querySelector(".del-btn").addEventListener("click", () => {
    if (!confirm(`Delete "${job.title || "this job"}" and all output files?\nThis cannot be undone.`)) return;
    fetch(`${BASE_URL}/jobs/${job.job_id}`, { method: "DELETE" }).then(res => {
      if (res.ok) { jobRow.remove(); detailRow.remove(); }
      else alert(`Delete failed (${res.status}).`);
    });
  });

  return { jobRow, detailRow, job, batchName };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}

async function patchJob(id, data) {
  await fetch(`${BASE_URL}/jobs/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─── Init ─────────────────────────────────────────────────────────────────────

// ─── Fold all / Expand all ────────────────────────────────────────────────────

function initFoldAll() {
  const btn = document.getElementById("fold-all-btn");
  if (!btn) return;
  let folded = false;
  btn.addEventListener("click", () => {
    const headers = document.querySelectorAll("tr.batch-header-row[data-week-key]");
    if (!folded) {
      headers.forEach(r => {
        const key = r.dataset.weekKey;
        if (!collapsedWeeks.has(key)) collapsedWeeks.add(key);
      });
      btn.textContent = "▸ Unfold";
      folded = true;
    } else {
      collapsedWeeks.clear();
      btn.textContent = "▾ Fold";
      folded = false;
    }
    render();
  });
}

load().catch(() => {
  document.getElementById("jobs-tbody").innerHTML =
    '<tr><td colspan="6" class="empty">Could not load — is the API running?</td></tr>';
});
initFoldAll();
