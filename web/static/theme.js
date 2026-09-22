(() => {
  const root = document.documentElement;
  const storageKey = "owlcam-theme";

  const readStoredTheme = () => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored === "light" || stored === "dark") return stored;
    } catch {
      /* private mode */
    }
    const attr = root.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    return "light";
  };

  const currentTheme = () =>
    root.getAttribute("data-theme") === "light" ? "light" : "dark";

  const syncToggle = (theme) => {
    const toggle = document.querySelector("#theme-toggle");
    if (!toggle) return;
    const toLight = theme === "dark";
    toggle.textContent = toLight ? "Light" : "Dark";
    toggle.setAttribute(
      "aria-label",
      toLight
        ? "Switch to light theme for easier reading"
        : "Switch to dark theme",
    );
    toggle.setAttribute("aria-pressed", String(theme === "light"));
  };

  const applyTheme = (theme, { persist = false } = {}) => {
    const next = theme === "light" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    if (persist) {
      try {
        localStorage.setItem(storageKey, next);
      } catch {
        /* private mode */
      }
    }
    syncToggle(next);
  };

  applyTheme(readStoredTheme());

  const bindToggle = () => {
    const toggle = document.querySelector("#theme-toggle");
    toggle?.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark", {
        persist: true,
      });
    });
    syncToggle(currentTheme());
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindToggle);
  } else {
    bindToggle();
  }
})();
