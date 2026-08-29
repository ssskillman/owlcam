const grid = document.querySelector("#moments-grid");
const controls = document.querySelectorAll("[data-sort-key]");
const status = document.querySelector("#sort-status");

if (grid && controls.length && status) {
  let activeKey = "timestamp";
  let direction = "asc";

  const sortMoments = (key) => {
    direction = key === activeKey && direction === "asc" ? "desc" : "asc";
    activeKey = key;

    const cards = [...grid.querySelectorAll(".moment-card")];
    cards.sort((left, right) => {
      const comparison = left.dataset[key].localeCompare(
        right.dataset[key],
        undefined,
        { numeric: true, sensitivity: "base" },
      );
      return direction === "asc" ? comparison : -comparison;
    });
    cards.forEach((card) => grid.append(card));

    controls.forEach((control) => {
      const active = control.dataset.sortKey === key;
      control.setAttribute("aria-pressed", String(active));
      control.dataset.direction = active ? direction : "";
    });

    const label = [...controls].find(
      (control) => control.dataset.sortKey === key,
    ).textContent;
    status.textContent = `Sorted by ${label.toLowerCase()}, ${
      direction === "asc" ? "oldest or A–Z first" : "newest or Z–A first"
    }.`;
  };

  controls.forEach((control) => {
    control.addEventListener("click", () => sortMoments(control.dataset.sortKey));
  });

  sortMoments("timestamp");
}
