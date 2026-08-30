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
| Serve | `publish-feed.sh --private` | Only devices signed in to the tailnet |
| Funnel | `publish-feed.sh --public` | Anyone on the internet with the URL |

Funnel is the current setting, so phones and browsers with no Tailscale account
can watch. See [Should the feed be public?](#should-the-feed-be-public) for the
decision and its costs. `publish-feed.sh` changes exposure only; use
`serve-stream.sh` when you also need to start capture.

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

### Surviving reboots

`serve-stream.sh` brings the feed up once and then forgets about it. For a feed
that comes back on its own, install the units instead:

```bash
./pi/scripts/install-services.sh
```

`owlcam-mediamtx`, `owlcam-stream`, and `owlcam-diagnostics` then start at boot
and restart within about five seconds of a failure. They are user units rather
than system units because the Pi has no passwordless sudo; the installer enables
lingering so they survive the SSH session ending and start without a login.

The diagnostics service binds to `127.0.0.1:8765`. Tailscale Serve maps the
tailnet-only `/diagnostics` path to it without changing the root HLS proxy. Its
allowlisted JSON contract contains SoC temperature, available memory,
one-minute load, three process-health booleans, optional nest climate
(`climate.temperatureC` / `humidityPercent` from a BME280 on I2C), and a
sample timestamp. It intentionally omits PIDs, command lines, usernames, and
filesystem details. Missing climate hardware reports `connected: false`
rather than invented numbers.

To add nest air and humidity, enable I2C (`raspi-config`), wire a BME280 to
3.3 V / GND / SDA (GPIO2) / SCL (GPIO3), then reinstall the diagnostics unit so
it can open `/dev/i2c-1`. DHT22 is not supported.

Do not run `serve-stream.sh` or the UDP publisher alongside the units. The
sensor takes exactly one consumer, so whichever loses the race restarts forever.

### Choosing a mode

The camera feeds exactly one destination at a time, and the two publishers are
mutually exclusive:

| Publisher | Destination | Who can watch |
|---|---|---|
| `pi/scripts/start-stream.sh` (units use this) | RTSP into MediaMTX, served as HLS | The web page, and any tailnet device via the HLS URL |
| `scripts/start_stream.sh` | MPEG-TS over UDP to one hardcoded IP | Only that one machine, in VLC |

The UDP path is a debugging convenience. It bypasses MediaMTX entirely, so while
it runs the web page correctly reports `no stream is available on path 'owl'`.
Prefer the RTSP path: MediaMTX can serve many readers at once, and VLC will open
the same tailnet HLS URL the browser uses.

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

**Decided 2026-08-30: yes, over Funnel.** The feed is a nature camera with no
private content, and requiring every viewer to install Tailscale and be added to
the tailnet defeated the point. Phones on cellular could not watch at all.

```bash
./pi/scripts/publish-feed.sh --public    # anyone with the URL
./pi/scripts/publish-feed.sh --private   # back to tailnet only
./pi/scripts/publish-feed.sh --status    # what is live right now
```

**One-time approval is required first.** The Pi needs the `funnel` node
attribute, and until it is granted `tailscale funnel` does not fail — it blocks
on the approval flow indefinitely. Worse, a blocked attempt that gets killed
after the old mounts were cleared takes the feed down for tailnet viewers too.
`publish-feed.sh --public` therefore checks for the attribute up front, refuses
with the approval URL, and leaves the live mounts alone:

```text
https://login.tailscale.com/f/funnel?node=<node-id>
```

Approve that in the admin console, then re-run `--public`. If a funnel attempt
ever does hang, `pkill -f "tailscale funnel"` clears it; check
`tailscale serve status` afterwards, because "No serve config" means the feed is
down and needs `publish-feed.sh --private` to come back.

Serve and Funnel apply per **port**, not per mount point, so the HLS root and
the `/diagnostics` mount are always declared together in the same mode. Going
public therefore also publishes the vitals payload. That payload is an allowlist
by design — no PIDs, paths, usernames, or addresses — which is what makes this
acceptable. Keep it that way.

`install-services.sh` calls `publish-feed.sh --preserve`, so reinstalling does
not quietly pull a public feed back to private.

### What this costs, and when to switch

The objections below are real and unchanged; they are accepted, not refuted.
Revisit the restream option in the table further down when any of them bites.

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

### Alternatives if Funnel stops being enough

The row that matters is the third one: it is the only option that scales past a
handful of simultaneous viewers.

| Approach | Public ingress | Cost per extra viewer | Notes |
|---|---|---|---|
| Share the `owlcam` machine on the tailnet | none | full bitrate | Already the documented control in [`security.md`](security.md). Best for a handful of people. |
| Publish snapshots or short clips to the existing page | none | zero | Firebase serves them. Reuses the Moments gallery pattern, and survives the Pi being offline. |
| Restream to YouTube or Facebook Live | none | zero | The Pi pushes one 2.5 Mbps connection upstream; the platform fans out to any audience size. |

Restreaming is the correct architecture for a large public audience: one
outbound stream regardless of how many people watch, no inbound port, and no
home-upload scaling problem. `security.md` already anticipates it by listing
Facebook stream keys as never-commit material. Funnel is the right trade only
while the audience is small enough that home upload is not the constraint.

## Cross-origin note

The page is served from `web.app` while the video comes from `ts.net`, so the
HLS response must allow the cross-origin read. The Pi's MediaMTX config sets
`hlsAllowOrigins: ['*']`, which satisfies this. If the feed loads by `curl` but
the player still reports it offline, check that setting first, then confirm the
Firebase CSP still lists the Tailscale host in `media-src` and `connect-src`.
