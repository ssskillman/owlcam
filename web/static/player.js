(() => {
  const video = document.querySelector("#owlcam-player");
  const panel = document.querySelector("#offline-panel");
  const retry = document.querySelector("#retry-stream");
  const status = document.querySelector("#stream-status");
  const dot = document.querySelector(".status-dot");
  let hls;

  if (!video || !panel || !retry || !status || !dot) return;

  const setState = (state, message) => {
    status.textContent = message;
    dot.classList.remove("online", "offline");
    dot.classList.add(state);
    panel.hidden = state === "online";
  };

  const showOffline = () => {
    setState("offline", "Private feed unavailable");
  };

  const connect = () => {
    const source = video.dataset.streamUrl;
    setState("", "Checking private feed…");

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
      });
      hls.on(window.Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) showOffline();
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
  });
  video.addEventListener("error", showOffline);
  retry.addEventListener("click", connect);
  connect();
})();
