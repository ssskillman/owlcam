# Future offerings

Parked 2026-09-16. These are product slices that fit the current split:
**Pi captures, PC classifies, Funnel is a small live audience.** None of this
is built. Do not start YOLO, BioCLIP, or a second encoder on the nest Pi.

Prerequisite for A, B, and E: stills (or short clips) extracted from
`rtsp://127.0.0.1:8554/owl`, queued on the Pi, POSTed to the PC identify
API over Tailscale, with retry when the PC is asleep. That watcher is not
in the tree yet. See [`../architecture.md`](../architecture.md) and
[`../next_steps.md`](../next_steps.md).

Do not swap the order below. Highlights and alerts are useless without a
visit log of classified stills. Sensors and restream do not depend on the
watcher.

## A. Real Moments / last-24h highlights

**Shipped (v1):** `/moments` includes a **From the nest** section that polls
the inference host visit API about every thirty seconds and shows
`feed_watcher` captures with known species (confidence ≥ 0.6). Curated
static cards in `web/static/moments/` remain above that section.

**E2E checklist:**

1. PC identifier + Funnel `:8443` healthy; Pi `owlcam-feed-watcher` running.
2. Open `/moments` — curated field log unchanged; live section loads or
   shows offline copy without breaking the page.
3. After a classified nest still (or a manual `feed_watcher` POST), a new
   card appears within one poll interval (~30s) without redeploy.
4. Thumbnail loads (no CSP errors for `OWLCAM_ANIMAL_ID_ORIGIN`).
5. PC asleep — live section shows unavailable; curated Moments still work.

**Later:** Pi sync of thumbnails to `~/owlcam/site` for same-origin cache when
the PC is off; daily “pick best of” curation; optional 2–3 s clips. A USB
SSD on the Pi remains the buffer if clip volume grows.

## B. Ping when it is a raccoon (or an owl)

Same classified stills, different destination. Slack incoming webhook,
email, or iMessage-via-email. Allowlist species (`raccoon`, `barred owl`)
and a cooldown (one raccoon ping per 30 minutes). Do not page on every
motion frame. Secrets stay in `~/.config/owlcam/`, never git
([`../security.md`](../security.md)).

## C. Nest temperature and humidity

The public diagnostics tiles already exist; they show **Not connected**
until a **BME280** is on I2C. Wiring, installer, and “never invent a
number” rules are in [`../next_steps.md`](../next_steps.md). This does
not need the PC or the watcher. Night IR / lux / PIR are listed there as
follow-ons, not this slice.

## D. YouTube or Facebook Live for a group

Funnel is the wrong tool for a crowd: one viewer is the full 2.5 Mbps
from the house; ten viewers is 25 Mbps; Tailscale Funnel is a funnel, not
a hose ([`../live-feed.md`](../live-feed.md)). Restream is one outbound
RTMPS/RTMP push; the platform fans out.

Facebook Groups: Live Producer + stream key, persistent key, member live
permission (admin not required). Key never in git. OwlCam URL stays the
always-on watch link; Facebook Live is an event with a start and a stop.
The Pi must be capturing (`owlcam-stream`) or ffmpeg has nothing to push.

## E. Visit log you can ask questions of later

A table of timestamp, species, confidence, thumbnail path, model version.
No photos in the identify history DB today on purpose; this log is
separate and can keep a thumbnail. Natural-language (“when did a raccoon
last show?”) is a query over this table on the PC, named in
[`../../CURSOR_HANDOFF_OWLCAM.md`](../../CURSOR_HANDOFF_OWLCAM.md). Do
not build a chatbot first. Egg/chick/prey/feeding and parent A vs B are
later labels on the same log.

## Explicitly not these

- Live bounding boxes burned into HLS (second encode on a 2 GB Pi 4).
- Unlimited concurrent live viewers on Funnel.
- Spark Hosting as a continuous clip dump (360 MB/day transfer).
- Asking for Facebook group admin just to restream.
- Running the species model on the Pi.
