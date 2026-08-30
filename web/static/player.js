(() => {
  const video = document.querySelector("#owlcam-player");
  const panel = document.querySelector("#offline-panel");
  const retry = document.querySelector("#retry-stream");
  const status = document.querySelector("#stream-status");
  const dot = document.querySelector(".status-dot");
  const title = document.querySelector("#offline-title");
  const message = document.querySelector("#offline-message");
  const RECONNECT_DELAY = 5000;
  let hls;
  let reconnectTimer;

  if (!video || !panel || !retry || !status || !dot) return;

  // "Camera is resting" was the panel's only headline, so a blocked request, a
  // dead network, and a genuinely idle camera all read as an owl taking a nap.
  // Each cause needs a different action from the viewer, so each gets its own copy.
  const REASONS = {
    connecting: {
      title: "Connecting to the camera",
      message: "Contacting the nest box. This usually takes a few seconds.",
    },
    resting: {
      title: "Camera is resting",
      message:
        "The nest box answered but is not streaming right now. The feed " +
        "reconnects automatically when OwlCam comes back online.",
    },
    interrupted: {
      title: "Stream interrupted",
      message:
        "The nest box is reachable and the video briefly stopped arriving. " +
        "Reconnecting automatically.",
    },
    unreachable: {
      title: "Cannot reach the camera",
      message:
        "The nest box did not answer at all. That is a network problem " +
        "between this device and the camera, not a sleeping camera. " +
        "Retrying automatically.",
    },
    unsupported: {
      title: "This browser cannot play the feed",
      message:
        "OwlCam streams HLS video, which this browser cannot decode. " +
        "Safari, Chrome, Firefox, and Edge all play it.",
    },
  };

  const explain = (reason) => {
    const copy = REASONS[reason];
    if (!copy || !title || !message) return;
    title.textContent = copy.title;
    message.textContent = copy.message;
  };

  // The player only knows that playback failed, never why. Asking the stream
  // URL directly separates "no answer" from "answered, nothing to play".
  const diagnose = async () => {
    try {
      const response = await fetch(video.dataset.streamUrl, {
        cache: "no-store",
      });
      return response.ok ? "interrupted" : "resting";
    } catch {
      return "unreachable";
    }
  };

  const setState = (state, message) => {
    status.textContent = message;
    dot.classList.remove("online", "offline");
    // The connecting state has no class of its own, and classList.add("")
    // throws a SyntaxError. Unguarded, that aborted connect() on its first
    // statement, so the player never ran at all.
    if (state) dot.classList.add(state);
    panel.hidden = state === "online";
  };

  const showOffline = () => {
    setState("offline", "Live feed unavailable");
  };

  const scheduleReconnect = () => {
    showOffline();
    // Fire and forget: the retry timer must not wait on a probe that may hang.
    diagnose().then(explain);
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
  };

  // hls.js buffers but never starts playback on its own. Without this the panel
  // hides, the status reads online, and the viewer stares at a paused first
  // frame — the stream is fine and nothing says so.
  const start = () => {
    const attempt = video.play();
    if (!attempt?.catch) return;
    attempt.catch(() => {
      // Muted playback is normally allowed to autoplay. If a browser refuses
      // anyway, say so, because the controls are the only way forward.
      if (video.paused) setState("online", "OwlCam online — press play");
    });
  };

  const connect = () => {
    const source = video.dataset.streamUrl;
    setState("", "Checking live feed…");
    explain("connecting");
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;

    if (hls) {
      hls.destroy();
      hls = undefined;
    }

    // hls.js must be tried before the native check. Chrome answers
    // canPlayType("application/vnd.apple.mpegurl") with "maybe" — truthy — but
    // cannot decode HLS on the desktop, so probing native support first strands
    // every browser except Safari on "Checking live feed…" forever.
    if (window.Hls?.isSupported()) {
      hls = new window.Hls({
        manifestLoadingTimeOut: 8000,
        levelLoadingTimeOut: 8000,
        fragLoadingTimeOut: 10000,
      });
      hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        setState("online", "OwlCam online");
        start();
      });
      hls.on(window.Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) scheduleReconnect();
      });
      hls.loadSource(source);
      hls.attachMedia(video);
      return;
    }

    // iOS Safari ships no MSE, so hls.js reports unsupported there and native
    // HLS is the genuine path rather than a guess.
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = source;
      video.load();
      return;
    }

    setState("offline", "This browser cannot play HLS video");
    explain("unsupported");
  };

  video.addEventListener("loadedmetadata", () => {
    setState("online", "OwlCam online");
    start();
  });

  // A live edge that stalls behind the playlist window never recovers on its
  // own, and a paused live stream is indistinguishable from a dead one.
  video.addEventListener("stalled", start);
  video.addEventListener("error", scheduleReconnect);
  retry.addEventListener("click", connect);
  connect();
})();
