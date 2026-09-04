// content.js — runs in the active tab

if (!window.__jaa_injected) {
  window.__jaa_injected = true;

  // Notify panel when this tab becomes active so it can auto-scope the job
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      try {
        chrome.runtime.sendMessage({ type: "tab_activated", url: window.location.href }).catch(() => {});
      } catch (_) {}
    }
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "extract") {
      clickSeeMore().then(() => {
        const ogSite = document.querySelector('meta[property="og:site_name"]');
        // Scope to job description container to avoid capturing premium preamble, nav, sidebar.
        // LinkedIn and Indeed both render the JD in specific containers.
        const descEl = document.querySelector(
          '.jobs-description__container, #job-details, .jobs-description-content__text, ' +
          '.job-details__content, #jobDescriptionText, .jobsearch-jobDescriptionText'
        ) || document.querySelector('main') || document.body;
        sendResponse({
          title:        document.title,
          url:          window.location.href,
          raw_text:     descEl.innerText,
          og_site_name: ogSite ? ogSite.content : ""
        });
      });
      return true;
    }

    if (msg.type === "fill_form") {
      fillForm(msg.profile, msg.experience || {}, msg.ats);
      sendResponse({ ok: true });
    }
  });
}

async function clickSeeMore() {
  const btn = document.querySelector(".jobs-description__footer-button")           // LinkedIn
    || document.querySelector("[data-testid='job-expander-button']")               // Indeed
    || document.querySelector("#jobDescriptionText button")                         // Indeed alt
    || [...document.querySelectorAll("button")].find(b => /^(see|show) more$/i.test(b.textContent.trim()));
  if (btn) { btn.click(); await new Promise(r => setTimeout(r, 500)); }
}

function setVal(el, value) {
  if (!el || value == null) return;
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const desc  = Object.getOwnPropertyDescriptor(proto, "value");
  if (desc && desc.set) desc.set.call(el, value);
  el.dispatchEvent(new Event("input",  { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

function qs(sel) { return document.querySelector(sel); }

function fillForm(p, exp, ats) {
  if (ats === "greenhouse") { fillGreenhouse(p); fillExperienceGreenhouse(exp); return; }
  if (ats === "lever")      { fillLever(p);      fillExperienceLever(exp);      return; }
  fillGeneric(p);
  fillExperienceGeneric(exp);
}

function fillGreenhouse(p) {
  const [first, ...rest] = (p.name || "").split(" ");
  setVal(document.getElementById("first_name"), first);
  setVal(document.getElementById("last_name"),  rest.join(" "));
  setVal(document.getElementById("email"),      p.email);
  setVal(document.getElementById("phone"),      p.phone);
  setVal(qs("input[id*='linkedin'], input[name*='linkedin']"), p.linkedin);
  setVal(qs("input[id*='github'],   input[name*='github']"),   p.github);
  setVal(qs("textarea[id*='cover'], textarea[name*='cover']"), p.cover_letter || "");
}

function fillLever(p) {
  setVal(qs("input[name='name']"),  p.name);
  setVal(qs("input[name='email']"), p.email);
  setVal(qs("input[name='phone']"), p.phone);
  setVal(qs("input[placeholder*='LinkedIn'], input[name*='linkedin']"), p.linkedin);
  setVal(qs("input[placeholder*='GitHub'],   input[name*='github']"),   p.github);
  setVal(qs("textarea[name*='comments'], textarea[name*='cover']"),     p.cover_letter || "");
}

const FIELD_KEYWORDS = [
  [["first name", "first_name", "firstname", "given name"], "first"],
  [["last name",  "last_name",  "lastname",  "surname"],    "last"],
  [["email"],                                               "email"],
  [["phone", "mobile", "tel"],                              "phone"],
  [["linkedin"],                                            "linkedin"],
  [["github"],                                              "github"],
  [["location", "city", "address"],                         "location"],
  [["cover letter", "coverl"],                              "cover"],
  [["summary", "about you"],                                "summary"],
  [["full name", "your name"],                              "name"],
];

const EEO_PATTERNS = /ethnicity|race|gender|veteran|disability|hispanic|latino|eeo|equal.opportun|demographic|pronouns|citizenship/i;

function classifyField(el) {
  const labelEl = el.id ? document.querySelector(`label[for="${el.id}"]`) : null;
  const text = [el.id, el.name, el.placeholder, el.getAttribute("aria-label"), labelEl?.textContent]
    .filter(Boolean).join(" ").toLowerCase();
  if (EEO_PATTERNS.test(text)) return null; // skip demographic / EEO fields
  for (const [patterns, key] of FIELD_KEYWORDS) {
    if (patterns.some(p => text.includes(p))) return key;
  }
  return null;
}

function fillGeneric(p) {
  const map = {
    first:    p.name?.split(" ")[0],
    last:     p.name?.split(" ").slice(1).join(" "),
    name:     p.name,
    email:    p.email,
    phone:    p.phone,
    linkedin: p.linkedin,
    github:   p.github,
    location: p.location,
    cover:    p.cover_letter || "",
    summary:  p.cover_letter || "",
  };
  const fields = document.querySelectorAll(
    "input[type='text'], input[type='email'], input[type='tel'], input:not([type]), textarea"
  );
  for (const field of fields) {
    const key = classifyField(field);
    if (key && map[key]) setVal(field, map[key]);
  }
}

// ─── Experience fill helpers ───────────────────────────────────────────────

function setSelect(el, value) {
  if (!el || !value) return;
  const opt = [...el.options].find(o =>
    o.value === value || o.text.toLowerCase().includes(value.toLowerCase())
  );
  if (opt) { opt.selected = true; el.dispatchEvent(new Event("change", { bubbles: true })); }
}

function clickAddButton(keywords) {
  const btns = document.querySelectorAll("button, a[role='button']");
  for (const btn of btns) {
    if (keywords.some(k => btn.textContent.trim().toLowerCase().includes(k))) {
      btn.click();
      return true;
    }
  }
  return false;
}

function fillExperienceGreenhouse(exp) {
  const jobs = (exp.experience || []);
  const edu  = (exp.education  || []);

  jobs.forEach((job, i) => {
    if (i > 0) {
      clickAddButton(["add employment", "add position", "add experience"]);
      // brief yield — Greenhouse renders the new row synchronously in most cases
    }
    const suffix = i === 0 ? "" : `_${i + 1}`;
    setVal(qs(`#employer_name${suffix}, input[name*='employer']`),      job.employer);
    setVal(qs(`#title${suffix}, input[name*='job_title'], input[name*='position']`), job.title);
    setVal(qs(`#location${suffix}, input[name*='location']`),            job.location);

    // Start date — Greenhouse uses month/year selects or a single date input
    const smSel = qs(`select[id*='start'][id*='month']${suffix ? `[id*='${suffix}']` : ""}`);
    const syInp = qs(`input[id*='start'][id*='year']${suffix ? `[id*='${suffix}']` : ""}, select[id*='start'][id*='year']`);
    if (smSel) setSelect(smSel, job.start_month);
    if (syInp) setVal(syInp, job.start_year);

    // End date / current
    if (job.current) {
      const cb = qs(`input[type='checkbox'][id*='current']`);
      if (cb && !cb.checked) cb.click();
    } else {
      const emSel = qs(`select[id*='end'][id*='month']`);
      const eyInp = qs(`input[id*='end'][id*='year'], select[id*='end'][id*='year']`);
      if (emSel) setSelect(emSel, job.end_month);
      if (eyInp) setVal(eyInp, job.end_year);
    }

    const desc = job.description || (job.bullets || []).join("\n");
    setVal(qs(`textarea[id*='description']${suffix ? `[id*='${suffix}']` : ""}`), desc);
  });

  edu.forEach((e, i) => {
    if (i > 0) clickAddButton(["add education", "add school"]);
    setVal(qs(`input[id*='school'], input[name*='school'], input[id*='institution']`), e.institution);
    setVal(qs(`input[id*='degree'], input[name*='degree']`),                           e.degree);
    setVal(qs(`input[id*='discipline'], input[id*='field'], input[name*='major']`),    e.field);
    setVal(qs(`input[id*='start'][id*='year'], select[id*='start'][id*='year']`),      e.start_year);
    setVal(qs(`input[id*='end'][id*='year'],   select[id*='end'][id*='year']`),         e.end_year);
    if (e.gpa) setVal(qs(`input[id*='gpa']`), String(e.gpa));
  });
}

function fillExperienceLever(exp) {
  const jobs = (exp.experience || []);

  jobs.forEach((job, i) => {
    if (i > 0) clickAddButton(["add position", "add experience", "add employment"]);
    setVal(qs(`input[name*='company'], input[placeholder*='Company']`),  job.employer);
    setVal(qs(`input[name*='title'],   input[placeholder*='Title']`),    job.title);
    setVal(qs(`input[name*='from'],    input[placeholder*='From']`),     `${job.start_month}/${job.start_year}`);
    if (!job.current) {
      setVal(qs(`input[name*='to'], input[placeholder*='To']`), `${job.end_month}/${job.end_year}`);
    }
    const desc = job.description || (job.bullets || []).join("\n");
    setVal(qs(`textarea[name*='summary'], textarea[placeholder*='Summary']`), desc);
  });
}

function fillExperienceGeneric(exp) {
  // Attempt mode: look for textarea fields that semantically match experience sections
  // and fill them with a prose block. Structural fields (separate employer/date inputs)
  // vary too much across custom sites to target reliably without known selectors.
  const jobs = exp.experience || [];
  if (!jobs.length) return;

  const expText = jobs.map(j => {
    const dates = j.current
      ? `${j.start_month}/${j.start_year} – Present`
      : `${j.start_month}/${j.start_year} – ${j.end_month}/${j.end_year}`;
    const bullets = (j.bullets || []).map(b => `• ${b}`).join("\n");
    return `${j.title} at ${j.employer} | ${j.location} | ${dates}\n${bullets}`;
  }).join("\n\n");

  const areas = document.querySelectorAll("textarea");
  for (const ta of areas) {
    const key = classifyField(ta);
    if (key === "cover" || key === "summary") continue; // already filled by profile
    const label = [ta.id, ta.name, ta.placeholder, ta.getAttribute("aria-label")]
      .filter(Boolean).join(" ").toLowerCase();
    if (/experience|employment|work history|background/.test(label)) {
      setVal(ta, expText);
      break;
    }
  }
}
