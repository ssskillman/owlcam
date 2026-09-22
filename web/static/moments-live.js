(() => {
  const root = document.querySelector(".nest-moments");
  const grid = document.querySelector("#nest-moments-grid");
  const status = document.querySelector("#nest-moments-status");

  if (!root || !grid || !status) return;

  const POLL_MS = 30_000;
  const MIN_CONFIDENCE = 0.6;
  const SOURCE = "feed_watcher";
  const OFFLINE_MESSAGE =
    "Live nest captures are unavailable right now. The curated field log below still works.";

  const origin = (root.dataset.apiOrigin || "").replace(/\/$/, "");
  let timerId = null;
  let hasRendered = false;
  let adminSession = { authenticated: false, csrfToken: null };
  let cachedVisits = [];
  let suppressedIds = new Set();

  const apiUrl = (path) => `${origin}${path}`;

  const loadSuppressed = async () => {
    try {
      const response = await fetch("/api/nest-visits-suppressed", {
        credentials: "omit",
        cache: "no-store",
      });
      if (!response.ok) return;
      const payload = await response.json();
      const ids = Array.isArray(payload.visitIds) ? payload.visitIds : [];
      suppressedIds = new Set(
        ids.filter((id) => typeof id === "number" && id > 0),
      );
    } catch {
      suppressedIds = new Set();
    }
  };

  const formatSpecies = (species) =>
    species
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const formatConfidence = (value) => `${Math.round(value * 100)}%`;

  const filterVisits = (visits) =>
    visits.filter(
      (visit) =>
        visit &&
        visit.is_unknown === false &&
        visit.source === SOURCE &&
        typeof visit.confidence === "number" &&
        visit.confidence >= MIN_CONFIDENCE &&
        visit.thumbnail_url &&
        !suppressedIds.has(visit.id),
    );

  const trashIcon = `
    <svg class="nest-moment-delete-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path fill="currentColor" d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"/>
    </svg>
  `;

  const buildCard = (visit) => {
    const card = document.createElement("article");
    card.className = "moment-card nest-moment-card";
    card.dataset.visitId = String(visit.id);

    const thumbHref = apiUrl(visit.thumbnail_url);
    const subject = formatSpecies(visit.species || "Unknown");
    const confidence = formatConfidence(visit.confidence);
    const deleteButton = adminSession.authenticated
      ? `<button type="button" class="nest-moment-delete" data-visit-id="${visit.id}" aria-label="Delete this capture">${trashIcon}</button>`
      : "";

    card.innerHTML = `
      <div class="moment-media">
        <a class="moment-thumb" href="${thumbHref}" target="_blank" rel="noopener noreferrer">
          <img src="${thumbHref}" alt="${subject} at the nest" loading="lazy" decoding="async" />
          <span class="thumb-hint">VIEW CAPTURE</span>
        </a>
        <span class="nest-moment-badge">NEST CAM</span>
        ${deleteButton}
      </div>
      <div class="moment-copy">
        <div class="moment-kicker">
          <span class="moment-type">PHOTO</span>
          <span>${visit.created_at || ""}</span>
        </div>
        <h2 class="nest-moment-subject">${subject}</h2>
        <p class="moment-story">
          Identified from the live nest feed with ${confidence} confidence.
        </p>
        <p class="moment-file">
          <span class="story-label">AUTO CAPTURE</span>
          · visit #${visit.id}
        </p>
      </div>
    `;
    return card;
  };

  const renderVisits = (visits) => {
    cachedVisits = visits;
    grid.replaceChildren();
    if (!visits.length) {
      status.textContent =
        "No nest captures to show yet. When the camera sees a known animal, it will appear here.";
      hasRendered = true;
      return;
    }
    visits.forEach((visit) => grid.append(buildCard(visit)));
    status.textContent = `Showing ${visits.length} recent nest capture${
      visits.length === 1 ? "" : "s"
    }. Updates about every thirty seconds.`;
    hasRendered = true;
  };

  const refreshAdminSession = async () => {
    try {
      const response = await fetch("/admin/api/session", { credentials: "include" });
      if (!response.ok) {
        adminSession = { authenticated: false, csrfToken: null };
        return;
      }
      const payload = await response.json();
      adminSession = {
        authenticated: Boolean(payload.authenticated),
        csrfToken: payload.csrfToken || null,
      };
    } catch {
      adminSession = { authenticated: false, csrfToken: null };
    }
  };

  const deleteVisitOnServer = async (visitId, csrfToken) => {
    const response = await fetch(`/admin/api/nest-visits/${visitId}`, {
      method: "DELETE",
      credentials: "include",
      headers: { "X-Owlcam-Csrf": csrfToken },
    });
    if (response.status === 403) {
      return { retry: true };
    }
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        detail = payload?.error?.message || detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return { retry: false };
  };

  const deleteVisit = async (visitId) => {
    await refreshAdminSession();
    if (!adminSession.authenticated || !adminSession.csrfToken) {
      window.alert("Sign in from ? to delete nest captures.");
      return;
    }
    try {
      let result = await deleteVisitOnServer(visitId, adminSession.csrfToken);
      if (result.retry) {
        await refreshAdminSession();
        if (!adminSession.csrfToken) {
          throw new Error("Session expired");
        }
        result = await deleteVisitOnServer(visitId, adminSession.csrfToken);
        if (result.retry) {
          throw new Error("Request verification failed");
        }
      }
      suppressedIds.add(visitId);
      const next = cachedVisits.filter((visit) => visit.id !== visitId);
      renderVisits(next);
    } catch {
      window.alert("Could not delete that capture. Try signing in again from ?");
    }
  };

  grid.addEventListener("click", (event) => {
    const button = event.target.closest(".nest-moment-delete");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    const visitId = Number.parseInt(button.dataset.visitId || "", 10);
    if (Number.isFinite(visitId)) {
      deleteVisit(visitId);
    }
  });

  window.addEventListener("owlcam-admin-session", (event) => {
    const detail = event.detail || {};
    adminSession = {
      authenticated: Boolean(detail.authenticated),
      csrfToken: detail.csrfToken || null,
    };
    if (hasRendered) {
      renderVisits(cachedVisits);
    }
  });

  const loadVisits = async () => {
    if (!origin) {
      status.textContent =
        "Live nest captures are not configured on this site build.";
      return;
    }
    if (!hasRendered) {
      status.textContent = "Loading recent nest captures…";
    }
    try {
      await loadSuppressed();
      const response = await fetch(
        apiUrl("/api/animal-identification/visits?limit=20"),
        { credentials: "omit", mode: "cors" },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const visits = filterVisits(payload.visits || []);
      renderVisits(visits);
    } catch {
      if (!hasRendered) {
        grid.replaceChildren();
      }
      status.textContent = OFFLINE_MESSAGE;
    }
  };

  const start = async () => {
    await refreshAdminSession();
    await loadVisits();
    if (timerId !== null) window.clearInterval(timerId);
    timerId = window.setInterval(loadVisits, POLL_MS);
  };

  start();
})();
