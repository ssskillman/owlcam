# Next steps

Living roadmap. The live feed, systemd units, and diagnostics panel are already
on `main`. Work below is what is left to do on the Pi, the site, and the nest.

## Waiting on a public domain

Always-up Firebase pages and a second USB camera (Arducam B0506) are
specified and **parked** until a buddy buys a public hostname for live
video. Do not ship Firebase HTML that still fetches `*.ts.net` — Tailscale
devices will not play. Full order, constraints, and e2e gates:

[`next-steps/always-up-and-camera-2.md`](next-steps/always-up-and-camera-2.md)

## Phase: hardware enhancements

Add physical sensors to the same Pi that already runs capture, MediaMTX, and
`owlcam-diagnostics`. The public page already has Nest air and Humidity tiles.
Without hardware they show **Not connected**. After wiring, the same JSON
contract fills those tiles. Extra sensors should follow that pattern: extend
the allowlisted diagnostics payload, never invent numbers.

### Nest temperature and humidity (BME280)

1. Enable I2C (`sudo raspi-config` → Interface Options → I2C).
2. Wire a **BME280** (not DHT22): 3.3 V, GND, SDA on GPIO2, SCL on GPIO3.
   Address `0x76` or `0x77` is auto-detected.
3. Confirm the bus: `i2cdetect -y 1` should show the chip.
4. Copy the latest repo to the Pi and reinstall user units so diagnostics can
   open `/dev/i2c-1`. Staging from the Mac comes first; the installer is what
   puts the new code into service (see
   [Getting a new commit onto the Pi](../README.md#getting-a-new-commit-onto-the-pi)):

```bash
# Mac
OWLCAM_SSH_IDENTITY=~/.ssh/owlcam_pi ./pi/scripts/deploy.sh
# Pi
cd /home/shawn/owlcam/deploy
./pi/scripts/install-services.sh
```

5. Hard-refresh the site on a tailnet device. Nest air and humidity should
   update every five seconds. Pi temperature stays the SoC die reading.

Details: [`live-feed.md`](live-feed.md).

### Other sensors (same Pi, same panel)

Candidates that fit the nest-box job, in likely order:

| Sensor | Why | How it should land |
| --- | --- | --- |
| IR illuminator / IR-cut | Night watch inside a dark box | Prefer Arducam B0506 (onboard IR-cut + 850 nm LEDs) as camera #2 after the public domain; see [`next-steps/always-up-and-camera-2.md`](next-steps/always-up-and-camera-2.md) |
| Light / lux | Know dusk vs a blocked lens | I2C (e.g. VEML7700) on the same bus as the BME280 |
| Occupancy / PIR or break-beam | Optional nest-visit cue, not a substitute for video | Debounce in diagnostics or a future snapshot trigger |
| Waterproof housing / cable gland | Wooded box, weather | Mechanical; keep I2C leads short and strain-relieved |
| External USB SSD | Local clip buffer before upload | Separate from Firebase Hosting quotas below |

Rules for any new reading:

- Add a named field on the private `/diagnostics` JSON allowlist.
- Missing hardware → `connected: false` (or `null`), never a fake value.
- Re-run `./pi/scripts/install-services.sh` after code or unit changes.
- Keep CPU temperature, nest air, and any future probes as distinct metrics.

## Phase: Moments storage (what Spark actually gives you)

Today Owl Moments are **static files on Firebase Hosting**
(`web/static/moments/`), not a Pi auto-uploader and not Cloud Storage.

On the **Spark (no-cost)** plan, Hosting storage is **10 GB** for the whole
project. That includes the site, every moment photo/clip, **and retained
previous Hosting releases**. Individual Hosting files cannot exceed **2 GB**.
Spark transfer is the tighter operational cap: **360 MB/day** (and a monthly
transfer ceiling on the same plan). A few large `webm` files plus a busy day of
views can hit transfer before you hit 10 GB on disk.

[Firebase Hosting quotas](https://firebase.google.com/docs/hosting/usage-quotas-pricing)
are independent of Cloud Storage. **Cloud Storage for Firebase is not on Spark**
as of 2026; a Pi that uploaded clips into a bucket would need **Blaze**, which
still has a no-cost GCS tier in some regions but is a billing account, not
“free Firebase.”

Practical takeaway: curated Moments on Hosting fit Spark easily (hundreds of
small clips if you prune old Hosting releases). Continuous Pi capture into the
cloud is a later, Blaze-or-self-hosted phase — not something Spark Hosting is
meant to absorb.

## Later (out of this phase)

- Snapshot extraction from the existing RTSP path, store-and-forward off-box.
- Facebook / public restream (needs an outbound publisher; Funnel is a
  different exposure decision — see [`live-feed.md`](live-feed.md)).
- Commit the live `/etc/mediamtx.yml` into `pi/config/` so `install.sh` can
  succeed from git alone.
