# Architecture

## Phase 0

The Raspberry Pi is an edge appliance. It owns camera capture, H.264 encoding,
and private live streaming. MediaMTX fans one camera publisher out to viewers,
which avoids competing camera processes.

```text
IMX708
  |
  v
rpicam-vid --inline --codec h264
  |
  v
FFmpeg -c:v copy
  |
  v
MediaMTX rtsp://127.0.0.1:8554/owl
  |                         |
  v                         v
HLS private viewer          Future snapshot extraction
```

The stream pipeline does not depend on internet access or the future home AI
server. Tailscale is the private management and remote-viewing transport; no
public router ports are required.

## Source of truth

The repository contains the reviewed MediaMTX configuration, exact publisher
command, dependency pin, and operating documentation. Direct edits on the Pi
should stop after this baseline is verified.

```text
GitHub repository
  |
local clone
  |
safe staged deployment over Tailscale SSH
  |
Raspberry Pi
```

## Deferred phases

Phase 1 will add systemd units, snapshots extracted from the existing RTSP
stream, and a persistent store-and-forward uploader. Home AI, event storage,
IR control, and Facebook Live are intentionally outside Phase 0.

Capture and upload will remain separate so loss of Wi-Fi, Tailscale, or the
home server cannot stop camera capture.
