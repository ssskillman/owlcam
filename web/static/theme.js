(() => {
  const root = document.documentElement;
  const toggle = document.querySelector("#theme-toggle");
  const storageKey = "owlcam-theme";

  const currentTheme = () =>
    root.getAttribute("data-theme") === "light" ? "light" : "dark";

  const applyTheme = (theme) => {
    const next = theme === "light" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      /* private mode */
    }
    if (!toggle) return;
    const toLight = next === "dark";
    toggle.textContent = toLight ? "Light" : "Dark";
    toggle.setAttribute(
      "aria-label",
      toLight
        ? "Switch to light theme for easier reading"
        : "Switch to dark theme",
    );
    toggle.setAttribute("aria-pressed", String(!toLight));
  };

  if (!root.getAttribute("data-theme")) {
    applyTheme("dark");
  } else {
    applyTheme(currentTheme());
  }

  toggle?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
})();
