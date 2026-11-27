(() => {
  "use strict";
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {});
    });
  }
  const root = document.documentElement;
  const button = document.getElementById("theme-toggle");
  if (!button) return;
  const stored = document.cookie.split("; ").find((part) => part.startsWith("itoms_theme="));
  const initial = stored ? decodeURIComponent(stored.split("=")[1]) : "light";
  root.setAttribute("data-bs-theme", initial === "dark" ? "dark" : "light");
  button.addEventListener("click", () => {
    const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    document.cookie = "itoms_theme=" + encodeURIComponent(next) + "; Path=/; SameSite=Lax; Secure";
  });
})();
