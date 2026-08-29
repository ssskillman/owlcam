# Getting the live feed visible

The public page at <https://carver-owlcam-72343.web.app> already contains a
working HLS player. It requests:

```text
https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

Until that URL answers, the page shows "Camera is resting". Nothing on the web
side needs to change to light it up.

## What has to be true

1. The Pi is capturing and MediaMTX is serving HLS on port 8888.
2. Port 443 on the Pi answers HTTPS for that HLS, via Tailscale.
3. The viewer's device is allowed to reach that hostname.

Point 3 is the decision that matters. Tailscale offers two ways to publish:

| Mode | Command | Who can watch |
|------|---------|---------------|
| Serve | `serve-stream.sh` | Only devices signed in to the tailnet |
| Funnel | `serve-stream.sh --public` | Anyone on the internet with the URL |

Serve keeps the current security posture: the page is public, the video is not.
Funnel is what makes the feed visible to family and friends who will never
install Tailscale, and it exposes the nest camera to the open internet.

## Bringing it up

On the Pi:

```bash
cd /home/shawn/owlcam/deploy
./pi/scripts/serve-stream.sh            # private, tailnet only
./pi/scripts/serve-stream.sh --public   # public over Funnel
./pi/scripts/serve-stream.sh --stop     # shut it all down
```

The script starts MediaMTX and the camera only if a capture is not already
running, waits for local HLS to answer, then enables Serve or Funnel and prints
the watch URL and the exposure level.

## Verifying from a laptop

```bash
tailscale ping --c 3 --timeout 5s 100.123.8.55
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

A `200` means the page will play. From a device off the tailnet, the same
`curl` only returns `200` when Funnel is enabled.

## Funnel prerequisites

Funnel needs, in the tailnet policy:

- HTTPS certificates enabled for the tailnet
- the `funnel` node attribute granted to the Pi

Without those, `tailscale funnel` refuses to start and the script exits
non-zero.

## Cross-origin note

The page is served from `web.app` while the video comes from `ts.net`, so the
HLS response must allow the cross-origin read. The Pi's MediaMTX config sets
`hlsAllowOrigins: ['*']`, which satisfies this. If the feed loads by `curl` but
the player still reports it offline, check that setting first, then confirm the
Firebase CSP still lists the Tailscale host in `media-src` and `connect-src`.
