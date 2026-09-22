(() => {
  const toast = document.querySelector("#capture-toast");
  const iconEl = document.querySelector("#capture-toast-icon");
  const countEl = document.querySelector("#capture-toast-count");
  const origin = (document.body?.dataset.apiOrigin || "").replace(/\/$/, "");

  if (!toast || !iconEl || !countEl || !origin) return;

  const POLL_MS = 60_000;
  const HOURS = 24;
  const ICON_MAX = 10;

  const renderCount = (count) => {
    if (count >= 1 && count <= ICON_MAX) {
      iconEl.src = `/assets/icons/numbers/${count}.png`;
      iconEl.alt = `${count} nest captures in the last ${HOURS} hours`;
      iconEl.hidden = false;
      countEl.hidden = true;
    } else {
      iconEl.hidden = true;
      countEl.hidden = false;
      countEl.textContent = String(count);
    }
    toast.hidden = false;
  };

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
      renderCount(count);
    } catch {
      toast.hidden = true;
    }
  };

  loadCount();
  window.setInterval(loadCount, POLL_MS);
})();
