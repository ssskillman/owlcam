# OwlCam

OwlCam is a headless Raspberry Pi wildlife camera. The Pi captures and encodes
video, publishes a private stream through MediaMTX, and will later queue
snapshots for analysis on a stronger home computer.

Phase 0 preserves the manually working stream before any service automation is
introduced. The source handoff is in
[`CURSOR_HANDOFF_OWLCAM.md`](CURSOR_HANDOFF_OWLCAM.md).

## Phase 0 status

The local repository scaffold and known-good publisher are prepared. The Pi is
currently offline, so its live inventory, exact MediaMTX version pin,
`/etc/mediamtx.yml`, and end-to-end HLS verification remain pending. The
installer intentionally fails closed until `pi/config/mediamtx.version` is
captured, and configuration deployment must not be used until
`pi/config/mediamtx.yml` has been reviewed and committed.

## Current architecture

```text
IMX708 camera
    |
rpicam-vid (H.264, 1920x1080, 30 fps)
    |
FFmpeg (copy, RTSP publish)
    |
MediaMTX path /owl
    +-- RTSP on 8554
    +-- HLS on 8888
```

Management and viewing are private over Tailscale. Do not expose SSH, RTSP, or
HLS with router port forwarding.

## Known-good manual stream

On the Pi, start MediaMTX in one terminal:

```bash
mediamtx /etc/mediamtx.yml
```

Then publish the camera in another from a repository clone:

```bash
./pi/scripts/start-stream.sh
```

After using the staging deploy script, the equivalent path on the Pi is:

```bash
/home/shawn/owlcam/deploy/pi/scripts/start-stream.sh
```

Known viewer endpoints:

- Viewer: `http://100.123.8.55:8888/owl`
- HLS playlist: `http://100.123.8.55:8888/owl/index.m3u8`
- RTSP source: `rtsp://100.123.8.55:8554/owl`

The numeric Tailscale address is recorded as the known endpoint, not as a LAN
address dependency.

## Bootstrap and deploy

The Pi must run 64-bit Raspberry Pi OS on `aarch64`.

```bash
./pi/scripts/install.sh
./pi/scripts/install.sh --check
./pi/scripts/deploy.sh --dry-run
./pi/scripts/deploy.sh
```

Deployment stages a narrow set of files under `/home/shawn/owlcam/deploy`.
Installing the staged MediaMTX configuration requires the explicit
`--install-config` flag and creates a timestamped backup first.

Runtime configuration belongs in `/etc/owlcam/owlcam.env`; use
[`.env.example`](.env.example) as a non-secret template.

## Validation

```bash
make check
ssh shawn@100.123.8.55 'rpicam-hello --list-cameras'
curl --fail --show-error http://100.123.8.55:8888/owl/index.m3u8
```

See [`docs/recovery.md`](docs/recovery.md) before changing the known-good
manual stream.
