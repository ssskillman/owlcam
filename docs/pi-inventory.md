# Raspberry Pi Inventory

## Capture status

Live recapture is pending because the Pi was offline on 2026-08-29. Values
below are reported by the project handoff and must be replaced or confirmed
from the live device before Phase 0 is declared complete.

## Handoff-reported baseline

| Item | Reported value |
| --- | --- |
| Model | Raspberry Pi 4 Model B Rev 1.5 |
| RAM | 2 GB |
| Hostname | `owlcam` |
| User | `shawn` |
| Architecture | `aarch64` |
| Kernel | `6.18.34+rpt-rpi-v8` |
| Camera | IMX708, 4608x2592, 10-bit RGGB |
| FFmpeg | `7.1.5-0+deb13u1+rpt2` |
| Tailscale IPv4 | `100.123.8.55` |
| MediaMTX binary | `/usr/local/bin/mediamtx` |
| MediaMTX config | `/etc/mediamtx.yml` |

Reported camera modes include 1536x864 at approximately 120 fps, 2304x1296
at approximately 56 fps, and 4608x2592 at approximately 14 fps.

## Required live capture

When the Pi is online, record the output of:

```bash
hostname
cat /proc/device-tree/model; echo
uname -a
cat /etc/os-release
hostname -I
tailscale ip -4
command -v rpicam-vid
command -v ffmpeg
command -v mediamtx
ffmpeg -version | head -1
mediamtx --version
rpicam-hello --list-cameras
systemctl list-unit-files | grep -Ei 'tailscale|mediamtx|owlcam' || true
```

Do not capture Wi-Fi profiles, environment files, private keys, or
`/var/lib/tailscale`.
