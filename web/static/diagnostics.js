(() => {
  const panel = document.querySelector("#diagnostics");
  const status = document.querySelector("#diagnostics-status");
  const habitatTemperature = document.querySelector(
    "#diagnostics-habitat-temperature",
  );
  const humidity = document.querySelector("#diagnostics-humidity");
  const pressure = document.querySelector("#diagnostics-pressure");
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
    !pressure ||
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

  const formatSampleTime = (iso) =>
    new Date(iso).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });

  const validateClimate = (climate) => {
    if (!climate || typeof climate.connected !== "boolean") {
      throw new Error("Unexpected diagnostics response");
    }
    if (climate.connected) {
      if (
        typeof climate.sensor !== "string" ||
        !Number.isFinite(climate.temperatureC) ||
        !Number.isFinite(climate.humidityPercent) ||
        !Number.isFinite(climate.pressureHpa) ||
        Number.isNaN(Date.parse(climate.sampledAt))
      ) {
        throw new Error("Unexpected diagnostics response");
      }
      return;
    }
    if (
      climate.temperatureC != null ||
      climate.humidityPercent != null ||
      climate.pressureHpa != null ||
      climate.sampledAt != null
    ) {
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
      pressure.textContent = `${climate.pressureHpa.toFixed(1)} hPa`;
    } else {
      habitatTemperature.textContent = "Not connected";
      humidity.textContent = "Not connected";
      pressure.textContent = "Not connected";
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

    const piUpdated = formatSampleTime(data.sampledAt);
    if (data.climate.connected && data.climate.sampledAt) {
      updated.textContent = `Nest air updated ${formatSampleTime(
        data.climate.sampledAt,
      )} · Pi vitals updated ${piUpdated}`;
    } else {
      updated.textContent = `Pi vitals updated ${piUpdated}`;
    }
    panel.dataset.state = data.allProcessesStable ? "online" : "degraded";
  };

  // "Diagnostics unavailable" covered an unreachable Pi, an erroring Pi, and a
  // Pi returning something unexpected. Those need different fixes, so they get
  // different words.
  const unavailableReason = (httpStatus) => {
    if (httpStatus === null) return "Cannot reach the Pi — retrying";
    if (httpStatus >= 400) return `Pi answered HTTP ${httpStatus} — retrying`;
    return "Unexpected vitals from the Pi — retrying";
  };

  const renderUnavailable = (httpStatus = null) => {
    status.textContent = unavailableReason(httpStatus);
    habitatTemperature.textContent = "—";
    humidity.textContent = "—";
    pressure.textContent = "—";
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
    // Stays null until the Pi answers, which is what separates "unreachable"
    // from "answered badly" in the message the viewer reads.
    let httpStatus = null;

    try {
      const response = await fetch(endpoint, {
        cache: "no-store",
        signal: controller.signal,
      });
      httpStatus = response.status;
      if (!response.ok) throw new Error(`Diagnostics HTTP ${response.status}`);
      const data = await response.json();
      render(data, validate(data));
    } catch {
      renderUnavailable(httpStatus);
    } finally {
      clearTimeout(timeout);
      setTimeout(refresh, POLL_INTERVAL);
    }
  };

  refresh();
})();
