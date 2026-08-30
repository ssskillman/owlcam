(() => {
  const video = document.querySelector("#owlcam-player");
  const panel = document.querySelector("#offline-panel");
  const retry = document.querySelector("#retry-stream");
  const status = document.querySelector("#stream-status");
  const dot = document.querySelector(".status-dot");
  const RECONNECT_DELAY = 5000;
  let hls;
  let reconnectTimer;

  if (!video || !panel || !retry || !status || !dot) return;

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
    setState("offline", "Private feed unavailable");
  };

  const scheduleReconnect = () => {
    showOffline();
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
    setState("", "Checking private feed…");
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;

    if (hls) {
      hls.destroy();
      hls = undefined;
    }

    // hls.js must be tried before the native check. Chrome answers
    // canPlayType("application/vnd.apple.mpegurl") with "maybe" — truthy — but
    // cannot decode HLS on the desktop, so probing native support first strands
    // every browser except Safari on "Checking private feed…" forever.
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
