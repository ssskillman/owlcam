(() => {
  const panel = document.querySelector("#diagnostics");
  const status = document.querySelector("#diagnostics-status");
  const habitatTemperature = document.querySelector(
    "#diagnostics-habitat-temperature",
  );
  const humidity = document.querySelector("#diagnostics-humidity");
  const temperature = document.querySelector("#diagnostics-temperature");
  const memory = document.querySelector("#diagnostics-memory");
  const load = document.querySelector("#diagnostics-load");
  const processes = document.querySelector("#diagnostics-processes");
  const updated = document.querySelector("#diagnostics-updated");
  const POLL_INTERVAL = 5000;
  const REQUEST_TIMEOUT = 4000;

  if (
    !panel ||
    !status ||
    !habitatTemperature ||
    !humidity ||
    !temperature ||
    !memory ||
    !load ||
    !processes ||
    !updated
  ) {
    return;
  }

  const endpoint = panel.dataset.diagnosticsUrl;

  const validateClimate = (climate) => {
    if (!climate || typeof climate.connected !== "boolean") {
      throw new Error("Unexpected diagnostics response");
    }
    if (climate.connected) {
      if (
        typeof climate.sensor !== "string" ||
        !Number.isFinite(climate.temperatureC) ||
        !Number.isFinite(climate.humidityPercent)
      ) {
        throw new Error("Unexpected diagnostics response");
      }
      return;
    }
    if (climate.temperatureC != null || climate.humidityPercent != null) {
      throw new Error("Unexpected diagnostics response");
    }
  };

  const validate = (data) => {
    const processValues = Object.values(data?.processes ?? {});
    if (
      !Number.isFinite(data?.temperatureC) ||
      !Number.isFinite(data?.memoryAvailableGiB) ||
      !Number.isFinite(data?.load1) ||
      processValues.length !== 3 ||
      !processValues.every((value) => typeof value === "boolean") ||
      typeof data?.allProcessesStable !== "boolean" ||
      Number.isNaN(Date.parse(data?.sampledAt))
    ) {
      throw new Error("Unexpected diagnostics response");
    }
    validateClimate(data?.climate);
    return processValues;
  };

  const renderClimate = (climate) => {
    if (climate.connected) {
      habitatTemperature.textContent = `${climate.temperatureC.toFixed(1)} °C`;
      humidity.textContent = `${climate.humidityPercent.toFixed(1)} %`;
      return;
    }
    habitatTemperature.textContent = "Not connected";
    humidity.textContent = "Not connected";
  };

  const render = (data, processValues) => {
    const stableCount = processValues.filter(Boolean).length;
    const loadLabel =
      data.load1 < 1 ? "LOW" : data.load1 < 2 ? "MODERATE" : "HIGH";

    renderClimate(data.climate);
    temperature.textContent = `${data.temperatureC.toFixed(1)} °C`;
    memory.textContent = `${data.memoryAvailableGiB.toFixed(1)} GiB`;
    load.textContent = `${data.load1.toFixed(2)} · ${loadLabel}`;
    processes.textContent = `${stableCount}/3 stable`;
    status.textContent = data.allProcessesStable
      ? "All three streaming processes stable"
      : "A streaming process needs attention";
    updated.textContent = `Updated ${new Date(data.sampledAt).toLocaleTimeString(
      [],
      { hour: "numeric", minute: "2-digit", second: "2-digit" },
    )}`;
    panel.dataset.state = data.allProcessesStable ? "online" : "degraded";
  };

  const renderUnavailable = () => {
    status.textContent = "Diagnostics unavailable — checking again";
    habitatTemperature.textContent = "—";
    humidity.textContent = "—";
    temperature.textContent = "—";
    memory.textContent = "—";
    load.textContent = "—";
    processes.textContent = "—";
    updated.textContent = "The live camera can continue without diagnostics";
    panel.dataset.state = "offline";
  };

  const refresh = async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

    try {
      const response = await fetch(endpoint, {
        cache: "no-store",
        mode: "cors",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Diagnostics HTTP ${response.status}`);
      const data = await response.json();
      render(data, validate(data));
    } catch {
      renderUnavailable();
    } finally {
      clearTimeout(timeout);
      setTimeout(refresh, POLL_INTERVAL);
    }
  };

  refresh();
})();
