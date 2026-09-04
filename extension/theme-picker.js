/* Shared theme picker for all extension pages.
   Renders colored circle swatches into every [data-theme-picker] element.
   Reads/writes the "jaa-theme" localStorage key used across all pages.
   Empty string = dark default (no data-theme attribute on body). */
(function () {
  const THEMES = [
    { key: "",       label: "Dark",   bg: "#111111", accent: "#22c55e" },
    { key: "warm",   label: "Warm",   bg: "#faf7f0", accent: "#c94010" },
    { key: "orange", label: "Orange", bg: "#1e1508", accent: "#f97316" },
    { key: "blue",   label: "Blue",   bg: "#111c30", accent: "#60a5fa" },
    { key: "pink",   label: "Pink",   bg: "#1c1020", accent: "#f472b6" },
  ];

  const LS_KEY = "jaa-theme";

  function applyTheme(key) {
    if (key) {
      document.body.dataset.theme = key;
    } else {
      delete document.body.dataset.theme;
    }
    localStorage.setItem(LS_KEY, key);
  }

  function currentKey() {
    return localStorage.getItem(LS_KEY) || "";
  }

  function renderInto(container) {
    container.style.cssText = "display:flex;align-items:center;gap:5px;";
    container.innerHTML = "";
    const active = currentKey();

    THEMES.forEach(t => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.title = t.label;
      const isActive = t.key === active;
      btn.style.cssText = [
        "width:14px", "height:14px", "border-radius:50%",
        `background:conic-gradient(${t.accent} 0deg 144deg,${t.bg} 144deg 360deg)`,
        `border:2px solid ${isActive ? t.accent : "transparent"}`,
        "cursor:pointer", "padding:0", "flex-shrink:0", "outline:none",
        `transform:${isActive ? "scale(1.3)" : "scale(1)"}`,
        "transition:transform 0.12s,border-color 0.12s",
      ].join(";");

      btn.addEventListener("click", () => {
        applyTheme(t.key);
        document.querySelectorAll("[data-theme-picker]").forEach(renderInto);
      });

      container.appendChild(btn);
    });
  }

  // Apply saved theme immediately (runs when script is parsed, body already in DOM)
  applyTheme(currentKey());

  function init() {
    document.querySelectorAll("[data-theme-picker]").forEach(renderInto);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
