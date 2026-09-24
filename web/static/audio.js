(() => {
  const video = document.querySelector("#owlcam-player");
  const fill = document.querySelector("#audio-meter-fill");
  const status = document.querySelector("#audio-status");

  if (!video || !fill || !status) return;

  // A nest box is silent most of the night, so an empty bar is the normal
  // case and has to be distinguishable from a feed that is not arriving.
  const QUIET_AFTER = 6000;
  // Speech and owl calls from inside a box sit far below full scale. Without
  // this the bar never visibly leaves zero even when the audio is fine.
  const METER_GAIN = 4;
  const FLOOR = 0.004;

  let context;
  let analyser;
  let samples;
  let frame;
  let lastSound = 0;

  const setLevel = (ratio) => {
    const clamped = Math.max(0, Math.min(1, ratio));
    fill.style.width = `${(clamped * 100).toFixed(1)}%`;
  };

  const stopMeter = () => {
    if (frame) cancelAnimationFrame(frame);
    frame = undefined;
    setLevel(0);
  };

  const measure = () => {
    analyser.getByteTimeDomainData(samples);
    let peak = 0;
    for (let index = 0; index < samples.length; index += 1) {
      const deviation = Math.abs(samples[index] - 128) / 128;
      if (deviation > peak) peak = deviation;
    }
    setLevel(peak * METER_GAIN);
    if (peak > FLOOR) {
      lastSound = performance.now();
      status.textContent = "Listening";
    } else if (performance.now() - lastSound > QUIET_AFTER) {
      status.textContent = "Listening — nest is quiet";
    }
    frame = requestAnimationFrame(measure);
  };

  // createMediaElementSource permanently re-routes the element's output
  // through the AudioContext, so a suspended context would leave the viewer
  // with a working mute button and no sound at all. The graph is therefore
  // built only after resume() has confirmed the context is running, which
  // requires the user gesture that unmuting already is.
  const attach = async () => {
    if (context) return context.state === "running";
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return false;
    const pending = new Context();
    try {
      await pending.resume();
    } catch {
      return false;
    }
    if (pending.state !== "running") return false;
    context = pending;
    analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    samples = new Uint8Array(analyser.fftSize);
    context.createMediaElementSource(video).connect(analyser);
    analyser.connect(context.destination);
    return true;
  };

  const sync = async () => {
    if (video.muted || video.volume === 0) {
      status.textContent = "Muted — use the speaker button to listen";
      stopMeter();
      return;
    }
    if (!(await attach())) {
      status.textContent = "This browser cannot meter nest audio";
      return;
    }
    status.textContent = "Listening";
    lastSound = performance.now();
    if (!frame) frame = requestAnimationFrame(measure);
  };

  // The element's own speaker button is the only mute control, so its
  // volumechange event is what starts and stops the meter.
  video.addEventListener("volumechange", sync);
  video.addEventListener("pause", stopMeter);
  video.addEventListener("play", sync);

  sync();
})();
