# Next phase: stills from the live feed

Handoff 2026-09-18. Build this before highlights, raccoon pings, or a visit
log ([future-enhancements.md](future-enhancements.md) A, B, E).

## What is already true

- Pi: `owlcam-stream` + `owlcam-mediamtx` + `owlcam-site`. HLS at
  `https://owlcam.tail31318f.ts.net/owl/index.m3u8`. Capture binds the CSI
  camera once; extra work must read `rtsp://127.0.0.1:8554/owl`, not
  `/dev/video`.
- PC: YOLO + BioCLIP at `POST /api/animal-identification` on
  `https://penns-gaming-pc.tail31318f.ts.net:8443`. Loopback `127.0.0.1:8767`.
  Models never run on the Pi.
- Identify in the browser is upload-only. There is no motion unit and no
  overnight clip archive in the tree.

## Proven 2026-09-18 (manual)

1. Stream was `inactive` while site/MediaMTX were `active`. Start it:

   ```bash
   systemctl --user start owlcam-stream.service
   systemctl --user is-active owlcam-stream owlcam-mediamtx owlcam-site
   ```

   All three `active`. Local playlist must not say `no stream is available`.

2. One JPEG from RTSP, then POST to the PC (run **on the Pi**):

   ```bash
   ffmpeg -y -rtsp_transport tcp -i rtsp://127.0.0.1:8554/owl \
     -frames:v 1 -update 1 -q:v 2 /tmp/feed.jpg
   curl -sS -m 90 -F "images=@/tmp/feed.jpg" \
     https://penns-gaming-pc.tail31318f.ts.net:8443/api/animal-identification
   ```

3. Empty perch returned `is_unknown: true`, `yolo_detection: null`,
   confidence ~0.19. That is a pass for the pipe and a correct refuse to
   classify wood.

4. Copy the still to the Mac. Run `scp` **from the Mac**, not from the Pi
   (`owlcam` on the Pi is `127.0.1.1`):

   ```bash
   scp -i ~/.ssh/owlcam_pi -o IdentitiesOnly=yes \
     shawn@owlcam:/tmp/feed.jpg ~/feed.jpg
   ```

## What to build

A user systemd unit on the Pi that:

1. Periodically (or on cheap motion) grabs a still from loopback RTSP.
2. Queues files on disk so a sleeping PC does not drop events.
3. POSTs multipart JPEGs to the PC identify API over Tailscale, with retry.
4. Cooldown so wind does not burn the identifier rate limit.

Do **not**: second CSI consumer, YOLO on the Pi, `pkill -x ffmpeg`, or
block `owlcam-stream` if the PC is down.

Optional later: 5-minute `ffmpeg -c copy -f segment` overnight files on a
USB SSD (~1.1 GB/hour at 2.5 Mbps). That is review tape, not identification.

## SSH (this Mac)

```
# Pi — add to ~/.ssh/config if missing:
Host owl-pi
    HostName 100.123.8.55
    User shawn
    IdentityFile ~/.ssh/owlcam_pi
    IdentitiesOnly yes

# PC (already used as penn-pc)
Host penn-pc
    HostName 100.118.135.9
    User sskil
    IdentityFile ~/.ssh/mac_to_windows
    IdentitiesOnly yes
```

```bash
ssh owl-pi          # or: ssh -i ~/.ssh/owlcam_pi -o IdentitiesOnly=yes shawn@owlcam
ssh penn-pc
```

On the PC, OpenSSH lands you in **cmd**. `Restart-ScheduledTask` is often
missing. After `git pull`:

```bat
schtasks /Query /TN "OwlCam animal identifier"
schtasks /End /TN "OwlCam animal identifier"
schtasks /Run /TN "OwlCam animal identifier"
curl.exe http://127.0.0.1:8767/api/health
```

If `/Query` says the task does not exist, run
`animal_identifier/windows/install-identifier-task.ps1` elevated once.

## Done when

- A still from a frame that actually shows a bird classifies as a bird (or
  unknown if it is truly empty).
- The grab+POST can run with nobody at a keyboard, without stopping the live
  page.
- Tests pin: RTSP URL, POST path, no YOLO on the Pi, cooldown exists.

## Automation in the repo

- Phase 0 (on Pi): [`../../pi/scripts/e2e-phase0-feed.sh`](../../pi/scripts/e2e-phase0-feed.sh)
- Phase 1 (on Pi): [`../../pi/scripts/e2e-phase1-capture-identify.sh`](../../pi/scripts/e2e-phase1-capture-identify.sh)
  with `OWLCAM_IDENTIFY_URL` set.
- Watcher: [`../../pi/scripts/feed_watcher.py`](../../pi/scripts/feed_watcher.py),
  unit [`../../pi/systemd/owlcam-feed-watcher.service`](../../pi/systemd/owlcam-feed-watcher.service),
  config [`../../pi/config/watcher.env.example`](../../pi/config/watcher.env.example).
- Visit log + optional Slack alerts on the inference PC:
  `GET /api/animal-identification/visits`, env
  [`../../pi/config/alerts.env.example`](../../pi/config/alerts.env.example).
