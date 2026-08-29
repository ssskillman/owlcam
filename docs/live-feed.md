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
curl -sSL -o /dev/null -w '%{http_code}\n' \
  https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

A `200` means the page will play. From a device off the tailnet, the same
`curl` only returns `200` when Funnel is enabled.

**Use `-L`.** MediaMTX answers the first request for a manifest with a `302` to
`?cookieCheck=1` and serves the playlist on the redirect. Browsers and hls.js
follow that automatically, so a bare `curl` without `-L` reports `302` on a feed
that is working perfectly. Do not chase that as a fault.

## Certificate and Funnel prerequisites

**The order matters, and getting it wrong produces a misleading error.**

Both Serve and Funnel need HTTPS certificates enabled for the whole tailnet
before either will work. That is a tailnet-wide setting, not a per-machine one:

1. Enable HTTPS certificates at <https://login.tailscale.com/admin/dns>.
2. Grant the `funnel` node attribute to the Pi. Tailscale surfaces this as an
   approval link of the form
   `https://login.tailscale.com/f/funnel?node=<node-id>`.

If you approve Funnel first and skip step 1, `tailscale funnel` still fails
with `Funnel is not enabled on your tailnet`. The message points at Funnel, but
the missing piece is the certificate setting, and `sudo` does not help. Confirm
step 1 landed before touching anything else:

```bash
sudo tailscale cert owlcam.tail31318f.ts.net
```

That succeeds and writes a key and certificate once certificates are enabled.
Until then it fails, and so will both Serve and Funnel.

### What enabling certificates costs

Issuing a certificate publishes `owlcam.tail31318f.ts.net` to the public
Certificate Transparency logs. The name becomes permanently discoverable by
anyone reading those logs. It does **not** become reachable — while the node is
Serve-only, connections from outside the tailnet are refused — but the hostname
itself is no longer private. Tailscale warns about this at enable time. There is
no way to publish a stream over HTTPS without accepting it.

## Should the feed be public?

**Recommendation: no, not over Funnel.** Keep `serve-stream.sh` on its private
default.

Funnel is the wrong tool for this particular job, by its author's own account.
Tailscale [documents](https://tailscale.com/docs/features/tailscale-funnel)
that Funnel traffic is subject to non-configurable bandwidth limits, and a
Tailscale engineer put it plainly: *"there is a bandwidth limit, it's a funnel,
not a hose... I would suggest setting up your media server inside your tailnet
for the best experience."* A 24/7 2.5 Mbps video stream is exactly the sustained
high-bandwidth case Funnel is not built for.

The bandwidth ceiling is not the only problem:

- **No authentication.** Funnel exposes port 443 to the entire internet with no
  auth, no rate limit, and no abuse controls. The page publishes the stream URL,
  so the URL is not a secret and cannot act as one.
- **Upload saturation.** Every viewer pulls the full bitrate from the house.
  Ten simultaneous viewers is 25 Mbps sustained upstream, which degrades the
  household connection along with the stream.
- **Nest disturbance.** This is an active barred owl nest. A publicly
  advertised live feed invites attention to a nest site, and the About page
  already narrows down whose property it is.

### Better ways to make it visible

If the goal is that family and friends can watch, in increasing order of effort:

| Approach | Public ingress | Cost per extra viewer | Notes |
|---|---|---|---|
| Share the `owlcam` machine on the tailnet | none | full bitrate | Already the documented control in [`security.md`](security.md). Best for a handful of people. |
| Publish snapshots or short clips to the existing page | none | zero | Firebase serves them. Reuses the Moments gallery pattern, and survives the Pi being offline. |
| Restream to YouTube or Facebook Live | none | zero | The Pi pushes one 2.5 Mbps connection upstream; the platform fans out to any audience size. |

The third row is the correct architecture for a genuinely public audience: one
outbound stream regardless of how many people watch, no inbound port, and no
home-upload scaling problem. `security.md` already anticipates it by listing
Facebook stream keys as never-commit material.

Funnel remains available behind `--public` for a deliberate, short-lived share.
It should not be the way the feed is normally published.

## Cross-origin note

The page is served from `web.app` while the video comes from `ts.net`, so the
HLS response must allow the cross-origin read. The Pi's MediaMTX config sets
`hlsAllowOrigins: ['*']`, which satisfies this. If the feed loads by `curl` but
the player still reports it offline, check that setting first, then confirm the
Firebase CSP still lists the Tailscale host in `media-src` and `connect-src`.
