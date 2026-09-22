(() => {
  const toast = document.querySelector("#capture-toast");
  const countEl = document.querySelector("#capture-toast-count");
  const origin = (document.body?.dataset.apiOrigin || "").replace(/\/$/, "");

  if (!toast || !countEl || !origin) return;

  const POLL_MS = 60_000;
  const HOURS = 24;

  const loadCount = async () => {
    try {
      const response = await fetch(
        `${origin}/api/animal-identification/visits/stats?hours=${HOURS}&source=feed_watcher`,
        { credentials: "omit", mode: "cors" },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const count = Number(payload.count);
      if (!Number.isFinite(count)) {
        throw new Error("invalid count");
      }
      countEl.textContent = String(count);
      toast.hidden = false;
    } catch {
      toast.hidden = true;
    }
  };

  loadCount();
  window.setInterval(loadCount, POLL_MS);
})();
