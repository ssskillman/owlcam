(() => {
  const panel = document.querySelector("#diagnostics");
  const status = document.querySelector("#diagnostics-status");
  const habitatTemperature = document.querySelector(
    "#diagnostics-habitat-temperature",
  );
  const humidity = document.querySelector("#diagnostics-humidity");
  const daylight = document.querySelector("#diagnostics-daylight");
  const temperature = document.querySelector("#diagnostics-temperature");
  const temperatureUnitButtons = document.querySelectorAll(
    "[data-temperature-unit]",
  );
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
    !daylight ||
    !temperature ||
    temperatureUnitButtons.length !== 2 ||
    !memory ||
    !load ||
    !processes ||
    !updated
  ) {
    return;
  }

  const endpoint = panel.dataset.diagnosticsUrl;
  let temperatureUnit = "f";
  let latestData = null;
  panel.dataset.temperatureUnit = temperatureUnit;

  const celsiusToFahrenheit = (value) => (value * 9) / 5 + 32;

  const formatTemperature = (value) => {
    if (temperatureUnit === "f") {
      return `${celsiusToFahrenheit(value).toFixed(1)} °F`;
    }
    return `${value.toFixed(1)} °C`;
  };

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
      habitatTemperature.textContent = formatTemperature(climate.temperatureC);
      humidity.textContent = `${climate.humidityPercent.toFixed(1)} %`;
    } else {
      habitatTemperature.textContent = "Not connected";
      humidity.textContent = "Not connected";
    }
    daylight.textContent = "Sensor needed";
  };

  const render = (data, processValues) => {
    latestData = data;
    const stableCount = processValues.filter(Boolean).length;
    const loadLabel =
      data.load1 < 1 ? "LOW" : data.load1 < 2 ? "MODERATE" : "HIGH";

    renderClimate(data.climate);
    temperature.textContent = formatTemperature(data.temperatureC);
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
    daylight.textContent = "—";
    temperature.textContent = "—";
    memory.textContent = "—";
    load.textContent = "—";
    processes.textContent = "—";
    updated.textContent = "The live camera can continue without diagnostics";
    panel.dataset.state = "offline";
  };

  temperatureUnitButtons.forEach((button) => {
    button.addEventListener("click", () => {
      temperatureUnit = button.dataset.temperatureUnit;
      panel.dataset.temperatureUnit = temperatureUnit;
      temperatureUnitButtons.forEach((candidate) => {
        candidate.setAttribute(
          "aria-pressed",
          String(candidate === button),
        );
      });
      if (latestData) {
        temperature.textContent = formatTemperature(latestData.temperatureC);
        renderClimate(latestData.climate);
      }
    });
  });

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
