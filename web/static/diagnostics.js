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
  const sparklineButtons = document.querySelectorAll(
    "[data-history-metric]",
  );
  const dialog = document.querySelector("#diagnostics-history-dialog");
  const dialogTitle = document.querySelector("#diagnostics-history-title");
  const dialogSummary = document.querySelector(
    "#diagnostics-history-summary",
  );
  const dialogChart = document.querySelector("#diagnostics-history-chart");
  const dialogClose = document.querySelector("#diagnostics-history-close");
  const POLL_INTERVAL = 5000;
  const REQUEST_TIMEOUT = 4000;
  const SPARKLINE_HOURS = 24;
  const HISTORY_HOURS = 720;
  const SVG_NS = "http://www.w3.org/2000/svg";

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
    !updated ||
    !dialog ||
    !dialogTitle ||
    !dialogSummary ||
    !dialogChart ||
    !dialogClose
  ) {
    return;
  }

  const endpoint = panel.dataset.diagnosticsUrl;
  let temperatureUnit = "f";
  let latestData = null;
  let historySamples = [];
  let openMetric = null;
  let dialogOpener = null;
  panel.dataset.temperatureUnit = temperatureUnit;

  const celsiusToFahrenheit = (value) => (value * 9) / 5 + 32;
  const temperatureValue = (value) => {
    if (!Number.isFinite(value)) return null;
    return temperatureUnit === "f" ? celsiusToFahrenheit(value) : value;
  };
  const metricDefinitions = {
    habitatTemperatureC: {
      label: "Nest air",
      unit: () => `°${temperatureUnit.toUpperCase()}`,
      value: (sample) => temperatureValue(sample.habitatTemperatureC),
      format: (value) => value.toFixed(1),
    },
    humidityPercent: {
      label: "Relative humidity",
      unit: () => "%",
      value: (sample) => sample.humidityPercent,
      format: (value) => value.toFixed(1),
    },
    pressureHpa: {
      label: "Barometric pressure",
      unit: () => "hPa",
      value: (sample) => sample.pressureHpa,
      format: (value) => value.toFixed(1),
    },
    temperatureC: {
      label: "Pi temperature",
      unit: () => `°${temperatureUnit.toUpperCase()}`,
      value: (sample) => temperatureValue(sample.temperatureC),
      format: (value) => value.toFixed(1),
    },
    memoryAvailableGiB: {
      label: "Memory available",
      unit: () => "GiB",
      value: (sample) => sample.memoryAvailableGiB,
      format: (value) => value.toFixed(1),
    },
    load1: {
      label: "1-minute load",
      unit: () => "",
      value: (sample) => sample.load1,
      format: (value) => value.toFixed(2),
    },
    stableProcessCount: {
      label: "Streaming processes",
      unit: () => "stable",
      value: (sample) => sample.stableProcessCount,
      format: (value) => value.toFixed(0),
    },
  };

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

  const svgElement = (name, attributes = {}) => {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });
    return element;
  };

  const metricPoints = (metric, hours) => {
    const definition = metricDefinitions[metric];
    const cutoff = Number.isFinite(hours)
      ? Date.now() - hours * 60 * 60 * 1000
      : 0;
    return historySamples
      .map((sample) => ({
        time: Date.parse(sample.sampledAt),
        value: definition.value(sample),
      }))
      .filter(
        (point) =>
          Number.isFinite(point.time) &&
          Number.isFinite(point.value) &&
          point.time >= cutoff,
      )
      .sort((a, b) => a.time - b.time);
  };

  const extent = (points) => {
    const values = points.map((point) => point.value);
    let minimum = Math.min(...values);
    let maximum = Math.max(...values);
    if (minimum === maximum) {
      const padding = Math.max(Math.abs(minimum) * 0.02, 0.1);
      minimum -= padding;
      maximum += padding;
    }
    return { minimum, maximum };
  };

  const pathFor = (points, width, height, padding = 0) => {
    const { minimum, maximum } = extent(points);
    const firstTime = points[0].time;
    const lastTime = points.at(-1).time;
    const timeSpan = Math.max(lastTime - firstTime, 1);
    return points
      .map((point, index) => {
        const x =
          padding +
          ((point.time - firstTime) / timeSpan) * (width - padding * 2);
        const y =
          padding +
          (1 - (point.value - minimum) / (maximum - minimum)) *
            (height - padding * 2);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  };

  const renderSparkline = (button) => {
    const metric = button.dataset.historyMetric;
    const definition = metricDefinitions[metric];
    const points = metricPoints(metric, SPARKLINE_HOURS);
    button.replaceChildren();
    if (!definition || points.length < 2) {
      const waiting = document.createElement("span");
      waiting.className = "diagnostics-sparkline-status";
      waiting.textContent = "Collecting trend";
      button.append(waiting);
      button.disabled = true;
      return;
    }

    const change = points.at(-1).value - points[0].value;
    const direction =
      Math.abs(change) < 0.001 ? "steady" : change > 0 ? "up" : "down";
    button.classList.remove(
      "diagnostics-sparkline--up",
      "diagnostics-sparkline--down",
      "diagnostics-sparkline--steady",
    );
    button.classList.add(`diagnostics-sparkline--${direction}`);
    button.disabled = false;

    const svg = svgElement("svg", {
      viewBox: "0 0 160 36",
      "aria-hidden": "true",
      focusable: "false",
    });
    svg.append(
      svgElement("path", {
        d: pathFor(points, 160, 36, 2),
        class: "diagnostics-sparkline-path",
      }),
    );
    const description = document.createElement("span");
    description.className = "diagnostics-sparkline-status";
    description.textContent = `${direction}, ${definition.format(
      Math.abs(change),
    )} ${definition.unit()} over 24 hours`;
    button.append(svg, description);
  };

  const renderSparklines = () => {
    sparklineButtons.forEach(renderSparkline);
  };

  const addCurrentSample = (data) => {
    const sample = {
      sampledAt: data.sampledAt,
      habitatTemperatureC: data.climate.connected
        ? data.climate.temperatureC
        : null,
      humidityPercent: data.climate.connected
        ? data.climate.humidityPercent
        : null,
      pressureHpa: data.climate.connected ? data.climate.pressureHpa : null,
      temperatureC: data.temperatureC,
      memoryAvailableGiB: data.memoryAvailableGiB,
      load1: data.load1,
      stableProcessCount: Object.values(data.processes).filter(Boolean).length,
    };
    historySamples = historySamples.filter(
      (candidate) => candidate.sampledAt !== sample.sampledAt,
    );
    historySamples.push(sample);
    const cutoff = Date.now() - HISTORY_HOURS * 60 * 60 * 1000;
    historySamples = historySamples.filter(
      (candidate) => Date.parse(candidate.sampledAt) >= cutoff,
    );
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
    addCurrentSample(data);
    renderSparklines();
    if (openMetric) renderHistoryChart(openMetric);
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
      renderSparklines();
      if (openMetric) renderHistoryChart(openMetric);
    });
  });

  const chartText = (text, x, y, anchor = "start") => {
    const label = svgElement("text", {
      x,
      y,
      "text-anchor": anchor,
      class: "diagnostics-history-axis-label",
    });
    label.textContent = text;
    return label;
  };

  const renderHistoryChart = (metric) => {
    const definition = metricDefinitions[metric];
    const points = metricPoints(metric);
    dialogTitle.textContent = `${definition.label} history`;
    dialogChart.replaceChildren();
    if (points.length < 2) {
      dialogSummary.textContent =
        "Collecting samples — the first trend appears after two readings.";
      return;
    }

    const width = 760;
    const height = 390;
    const margin = { top: 24, right: 24, bottom: 54, left: 68 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const { minimum, maximum } = extent(points);
    const actualMinimum = Math.min(...points.map((point) => point.value));
    const actualMaximum = Math.max(...points.map((point) => point.value));
    const first = points[0];
    const last = points.at(-1);
    const span = last.time - first.time;
    const change = last.value - first.value;
    const unit = definition.unit();
    const unitSuffix = unit ? ` ${unit}` : "";
    const svg = svgElement("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-labelledby": "diagnostics-history-svg-title",
    });
    const title = svgElement("title", {
      id: "diagnostics-history-svg-title",
    });
    title.textContent = `${definition.label} history`;
    svg.append(title);

    for (let index = 0; index < 5; index += 1) {
      const ratio = index / 4;
      const y = margin.top + ratio * plotHeight;
      const value = maximum - ratio * (maximum - minimum);
      svg.append(
        svgElement("line", {
          x1: margin.left,
          y1: y,
          x2: width - margin.right,
          y2: y,
          class: "diagnostics-history-gridline",
        }),
        chartText(
          definition.format(value),
          margin.left - 12,
          y + 4,
          "end",
        ),
      );
    }

    const timeSpan = Math.max(last.time - first.time, 1);
    const formatTick = (time) => {
      if (span < 60 * 60 * 1000) {
        return time.toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit",
        });
      }
      if (span < 48 * 60 * 60 * 1000) {
        return time.toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        });
      }
      return time.toLocaleDateString([], {
        month: "short",
        day: "numeric",
      });
    };
    for (let index = 0; index < 5; index += 1) {
      const ratio = index / 4;
      const x = margin.left + ratio * plotWidth;
      const time = new Date(first.time + ratio * timeSpan);
      svg.append(
        svgElement("line", {
          x1: x,
          y1: margin.top,
          x2: x,
          y2: height - margin.bottom,
          class: "diagnostics-history-gridline",
        }),
        chartText(formatTick(time), x, height - 24, "middle"),
      );
    }

    const scaledPoints = points.map((point) => ({
      time: margin.left + ((point.time - first.time) / timeSpan) * plotWidth,
      value:
        margin.top +
        (1 - (point.value - minimum) / (maximum - minimum)) * plotHeight,
    }));
    svg.append(
      svgElement("path", {
        d: scaledPoints
          .map(
            (point, index) =>
              `${index === 0 ? "M" : "L"}${point.time.toFixed(
                2,
              )},${point.value.toFixed(2)}`,
          )
          .join(" "),
        class: "diagnostics-history-line",
      }),
      chartText(unit, 18, margin.top + plotHeight / 2, "middle"),
    );
    dialogChart.append(svg);
    dialogChart.setAttribute(
      "aria-label",
      `${definition.label} from ${definition.format(
        first.value,
      )} to ${definition.format(last.value)} ${unit}`,
    );
    dialogSummary.textContent = `Current ${definition.format(
      last.value,
    )}${unitSuffix} · Low ${definition.format(
      actualMinimum,
    )}${unitSuffix} · High ${definition.format(
      actualMaximum,
    )}${unitSuffix} · Change ${change >= 0 ? "+" : ""}${definition.format(
      change,
    )}${unitSuffix}`;
  };

  sparklineButtons.forEach((button) => {
    button.addEventListener("click", () => {
      openMetric = button.dataset.historyMetric;
      dialogOpener = button;
      renderHistoryChart(openMetric);
      dialog.showModal();
      dialogClose.focus();
    });
  });

  const closeDialog = () => {
    dialog.close();
    openMetric = null;
    dialogOpener?.focus();
  };
  dialogClose.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDialog();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });
  dialog.addEventListener("close", () => {
    openMetric = null;
  });

  const refreshHistory = async () => {
    try {
      const response = await fetch(`${endpoint}/history?hours=${HISTORY_HOURS}`, {
        cache: "no-store",
      });
      if (!response.ok) return;
      const payload = await response.json();
      if (!Array.isArray(payload?.samples)) return;
      historySamples = payload.samples.filter(
        (sample) => !Number.isNaN(Date.parse(sample?.sampledAt)),
      );
      if (latestData) addCurrentSample(latestData);
      renderSparklines();
    } catch {
      // Live diagnostics still work when the optional history request fails.
    }
  };

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

  refreshHistory();
  refresh();
})();
