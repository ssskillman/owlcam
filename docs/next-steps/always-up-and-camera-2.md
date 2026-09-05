# Next: always-up site, then camera #2

Parked 2026-09-05. Do not start this until a **public domain** exists
(buddy buys it). Current live system stays Pi-hosted, one origin, camera #1
only. See [`../next_steps.md`](../next_steps.md) for other nest hardware.

## Why this is waiting

The public page lives on the Pi so it shares an origin with HLS. If the Pi
or Funnel is down, the **whole website** is down. That is a trade from
2026-08-30, not a requirement. Details:
[`../live-feed.md`](../live-feed.md#why-one-origin).

Putting HTML back on Firebase **while** video still loads from
`owlcam.tail31318f.ts.net` will break every device running Tailscale:
MagicDNS turns that name into `100.123.8.55`, and the browser blocks a
public page from touching private address space.

## Order (do not swap)

1. **Public media hostname** — DNS for a custom domain (for example
   `live.carverowlcam.com`) must be Funnel's **public** IP, not `100.x`.
2. **Always-up site** — Firebase serves the real HTML again. Share link
   stays `https://carver-owlcam-72343.web.app`. Pi down → page still
   loads; player shows unreachable. HLS and `/diagnostics` use the public
   domain. Restore CORS/`hlsAllowOrigins`. Admin stays on the Pi origin
   (cookies/CSRF).
3. **Prove it** — Funnel or `owlcam-site` stopped: site still opens.
   Phone with Tailscale still plays. Phone without Tailscale still plays.
4. **Camera #2** — Arducam B0506 (OV2710 UVC, SKU B0506) as a **second
   publisher**, MediaMTX path `/owl2`, Funnel mount `/owl2`. Do **not**
   switch a single encoder between sensors. Each browser picks `/owl` or
   `/owl2` locally (`sessionStorage`). Default remains camera #1.

## Camera #2 constraints (when you get here)

- CSI IMX708 stays on `/owl` via `rpicam-vid`. UVC is a different
  `/dev/video*` than Unicam `video0`/`video1`.
- MJPG only (not YUY2). No USB microphone on HLS.
- Pi 4 has one H.264 block; cam1 already uses it at 1080p30. First cam2
  target: **1280×720 ~15–20 fps**.
- Stop/install scripts must not `pkill -x ffmpeg` (that kills camera #1).
- Independent admin toggles for two systemd units.

## E2E when building camera #2

Gate 0: camera #1 `/owl` still advancing on Funnel after every slice.

Then: UVC is not Unicam → both loopback playlists → both Funnel paths →
two browsers, swap on A does not change B → admin stop cam1 does not stop
cam2 → CI asserts `/owl2` mounts and no global ffmpeg kill.

Always `curl -L` MediaMTX playlists (cookieCheck 302).

## Out of scope until the domain exists

- Replacing camera #1 with B0506
- Firebase HTML + `*.ts.net` media
- 1080p30 on camera #2 as the first target
