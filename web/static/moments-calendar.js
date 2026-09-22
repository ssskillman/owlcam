(() => {
  const root = document.querySelector(".moments-calendar");
  if (!root) return;

  const grid = document.querySelector("#moments-calendar-grid");
  const monthLabel = document.querySelector("#moments-calendar-month");
  const prevButton = document.querySelector("#moments-calendar-prev");
  const nextButton = document.querySelector("#moments-calendar-next");
  const dayTitle = document.querySelector("#moments-day-title");
  const dayStatus = document.querySelector("#moments-day-status");
  const dayTable = document.querySelector("#moments-day-table");
  const dayBody = document.querySelector("#moments-day-body");

  if (
    !grid ||
    !monthLabel ||
    !prevButton ||
    !nextButton ||
    !dayTitle ||
    !dayStatus ||
    !dayTable ||
    !dayBody
  ) {
    return;
  }

  const SOURCE = "feed_watcher";
  const origin = (root.dataset.apiOrigin || "").replace(/\/$/, "");
  const weekdayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth() + 1;
  let selectedDate = null;
  let dayMap = new Map();

  const apiUrl = (path) => `${origin}${path}`;

  const pad = (value) => String(value).padStart(2, "0");

  const dateKey = (year, month, day) =>
    `${year}-${pad(month)}-${pad(day)}`;

  const monthName = (year, month) =>
    new Date(year, month - 1, 1).toLocaleString(undefined, {
      month: "long",
      year: "numeric",
    });

  const formatSpecies = (species) =>
    species
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const formatTime = (value) => {
    const parsed = new Date(value.replace(" ", "T"));
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const kindLabel = (kind) => {
    switch (kind) {
      case "entrance":
        return "Entrance";
      case "exit":
        return "Exit";
      case "pic":
        return "Photo saved";
      default:
        return "Motion";
    }
  };

  const renderCalendar = () => {
    monthLabel.textContent = monthName(viewYear, viewMonth);
    grid.replaceChildren();

    const leading = new Date(viewYear, viewMonth - 1, 1).getDay();
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();

    weekdayLabels.forEach((label) => {
      const head = document.createElement("div");
      head.className = "moments-calendar__weekday";
      head.textContent = label;
      grid.append(head);
    });

    for (let index = 0; index < leading; index += 1) {
      const padCell = document.createElement("div");
      padCell.className = "moments-calendar__day moments-calendar__day--pad";
      padCell.setAttribute("aria-hidden", "true");
      grid.append(padCell);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const key = dateKey(viewYear, viewMonth, day);
      const stats = dayMap.get(key) || {
        visits: 0,
        entrances: 0,
        exits: 0,
        pics: 0,
      };
      const button = document.createElement("button");
      button.type = "button";
      button.className = "moments-calendar__day";
      if (key === selectedDate) {
        button.classList.add("moments-calendar__day--selected");
      }
      if (
        key ===
        dateKey(today.getFullYear(), today.getMonth() + 1, today.getDate())
      ) {
        button.classList.add("moments-calendar__day--today");
      }
      button.dataset.date = key;
      button.innerHTML = `
        <span class="moments-calendar__daynum">${day}</span>
        <span class="moments-calendar__stats" aria-hidden="true">
          <span title="Visits">V ${stats.visits}</span>
          <span title="Exits">E ${stats.exits}</span>
          <span title="Photos">P ${stats.pics}</span>
        </span>
      `;
      const summary = `${stats.visits} visits, ${stats.exits} exits, ${stats.pics} photos`;
      button.setAttribute("aria-label", `${key}: ${summary}`);
      grid.append(button);
    }
  };

  const renderDayTable = (events) => {
    dayBody.replaceChildren();
    if (!events.length) {
      dayTable.hidden = true;
      dayStatus.textContent = "No nest activity logged for this day.";
      return;
    }
    dayTable.hidden = false;
    dayStatus.textContent = `${events.length} logged event${
      events.length === 1 ? "" : "s"
    }.`;
    events.forEach((event) => {
      const row = document.createElement("tr");
      const photoCell = document.createElement("td");
      if (event.thumbnail_url) {
        const link = document.createElement("a");
        link.href = `${origin}${event.thumbnail_url}`;
        link.textContent = "View";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        photoCell.append(link);
      } else {
        photoCell.textContent = "—";
      }
      const confidence =
        typeof event.confidence === "number"
          ? `${Math.round(event.confidence * 100)}%`
          : "—";
      row.innerHTML = `
        <td>${formatTime(event.time)}</td>
        <td>${kindLabel(event.kind)}</td>
        <td>${formatSpecies(event.species)}</td>
        <td>${confidence}</td>
      `;
      row.append(photoCell);
      dayBody.append(row);
    });
  };

  const loadDay = async (date) => {
    selectedDate = date;
    renderCalendar();
    dayTitle.textContent = new Date(`${date}T12:00:00`).toLocaleDateString(
      undefined,
      { weekday: "long", month: "long", day: "numeric", year: "numeric" },
    );
    dayStatus.textContent = "Loading activity…";
    dayTable.hidden = true;
    try {
      const response = await fetch(
        apiUrl(
          `/api/animal-identification/visits/day?date=${encodeURIComponent(
            date,
          )}&source=${encodeURIComponent(SOURCE)}`,
        ),
        { credentials: "omit", mode: "cors", cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      renderDayTable(Array.isArray(payload.events) ? payload.events : []);
    } catch {
      dayStatus.textContent =
        "Could not load this day. The visit log may be offline.";
      dayTable.hidden = true;
    }
  };

  const loadMonth = async () => {
    grid.setAttribute("aria-busy", "true");
    try {
      if (!origin) {
        throw new Error("missing api origin");
      }
      const response = await fetch(
        apiUrl(
          `/api/animal-identification/visits/calendar?year=${viewYear}&month=${viewMonth}&source=${encodeURIComponent(
            SOURCE,
          )}`,
        ),
        { credentials: "omit", mode: "cors", cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      dayMap = new Map(
        (payload.days || []).map((day) => [day.date, day]),
      );
      renderCalendar();
      if (!selectedDate) {
        const todayKey = dateKey(
          today.getFullYear(),
          today.getMonth() + 1,
          today.getDate(),
        );
        if (
          viewYear === today.getFullYear() &&
          viewMonth === today.getMonth() + 1
        ) {
          await loadDay(todayKey);
        }
      }
    } catch {
      dayMap = new Map();
      renderCalendar();
      dayStatus.textContent =
        "Nest activity calendar is unavailable while the visit log is offline.";
    } finally {
      grid.removeAttribute("aria-busy");
    }
  };

  prevButton.addEventListener("click", () => {
    viewMonth -= 1;
    if (viewMonth < 1) {
      viewMonth = 12;
      viewYear -= 1;
    }
    selectedDate = null;
    loadMonth();
  });

  nextButton.addEventListener("click", () => {
    viewMonth += 1;
    if (viewMonth > 12) {
      viewMonth = 1;
      viewYear += 1;
    }
    selectedDate = null;
    loadMonth();
  });

  grid.addEventListener("click", (event) => {
    const button = event.target.closest(".moments-calendar__day");
    if (!button || !button.dataset.date) return;
    loadDay(button.dataset.date);
  });

  loadMonth();
})();
