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

Management and viewing are private over Tailscale. Do not expose SSH, RTSP,
HLS, or UDP port 5000 with router port forwarding.

Do not run the MediaMTX publisher and the UDP publisher at the same time. The
physical camera can only be owned by one `rpicam-vid` process.

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

## Raspberry Pi UDP streaming

OwlCam can also send H.264 as MPEG-TS over UDP through Tailscale to a receiver.
FFmpeg copies the camera bitstream (`-c:v copy`) and does not re-encode.

The destination `100.116.197.91` is a Tailscale address. Both the Pi and the
receiver must be on the same tailnet. Do not replace this with a LAN IP in
scripts that should keep working after a house move.

### Requirements

The Raspberry Pi requires:

- Raspberry Pi OS
- `rpicam-vid`
- `ffmpeg`
- Tailscale connectivity to the receiving server

Verify the tools are installed:

```bash
rpicam-vid --version
ffmpeg -version
tailscale status
```

### Start the stream

From the repository root, on the Pi:

```bash
./scripts/start_stream.sh
```

The default stream destination is:

```text
udp://100.116.197.91:5000
```

The default video settings are:

- 1920x1080
- 30 FPS
- H.264
- MPEG-TS
- UDP packet size 1316

### Override the destination

```bash
OWL_CAM_DEST_IP=100.x.x.x \
OWL_CAM_DEST_PORT=5000 \
./scripts/start_stream.sh
```

### Override camera settings

```bash
OWL_CAM_WIDTH=1280 \
OWL_CAM_HEIGHT=720 \
OWL_CAM_FRAMERATE=30 \
./scripts/start_stream.sh
```

### Stop the stream

Press Ctrl+C.

### Test the UDP receiver

On the destination machine:

```bash
ffplay "udp://0.0.0.0:5000"
```

or:

```bash
ffmpeg \
  -i "udp://0.0.0.0:5000" \
  -f null -
```

The known-good VLC receiver used during LAN/Tailscale testing:

```bash
/Applications/VLC.app/Contents/MacOS/VLC \
  --network-caching=500 \
  "udp://@:5000"
```
