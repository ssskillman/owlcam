# Recovery

Phase 0 preserves the manual path. Do not replace it until the repository
version has been tested side by side.

## Connectivity

Check Tailscale before assuming the Pi's LAN address:

```bash
tailscale status
ssh shawn@100.123.8.55
```

If the Pi cannot join site Wi-Fi, enable its preconfigured phone hotspot,
wait up to two minutes, and retry Tailscale SSH.

## Camera

```bash
rpicam-hello --list-cameras
```

Expected camera index `0` is an IMX708. Power down before inspecting or
reseating the ribbon cable.

## Manual stream recovery

Stop only the failed publisher or MediaMTX process; do not start a second
physical-camera process.

```bash
mediamtx /etc/mediamtx.yml
```

In a second terminal from the deployed repository:

```bash
./pi/scripts/start-stream.sh
```

Verify locally on the Pi before testing through Tailscale:

```bash
ffprobe -v error rtsp://127.0.0.1:8554/owl
```

Then verify the remote HLS playlist:

```bash
curl --fail --show-error \
  http://100.123.8.55:8888/owl/index.m3u8
```

## Configuration rollback

The deploy script prints the timestamped backup path it creates before an
explicit configuration install. List the backups and choose the intended one:

```bash
ls -lt /etc/mediamtx.yml.bak.*
sudo cp /etc/mediamtx.yml.bak.YYYYMMDDTHHMMSSZ /etc/mediamtx.yml
```

Restart the manually launched MediaMTX process after rollback. Phase 0 does not
install or claim systemd services.

## Expected outage behavior

Loss of internet, Tailscale, the home computer, or a viewer must not be treated
as a camera failure. The local publisher and MediaMTX should continue running.
