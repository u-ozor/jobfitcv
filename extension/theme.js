// theme.js
(function () {
  const btn   = document.getElementById("theme-btn");
  const saved = localStorage.getItem("tracking-theme");
  if (saved === "dark") {
    document.body.classList.add("dark");
    btn.textContent = "light";
  }
  btn.addEventListener("click", function () {
    const isDark = document.body.classList.toggle("dark");
    btn.textContent = isDark ? "light" : "dark";
    localStorage.setItem("tracking-theme", isDark ? "dark" : "light");
  });
})();
