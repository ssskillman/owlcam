# OwlCam — session handoff (IR, GPIO admin, deploy, buddy-house stream)

**Date:** 2026-09-28  
**Repo:** [github.com/ssskillman/owlcam](https://github.com/ssskillman/owlcam)  
**Pi:** `shawn@100.123.8.55` (Tailscale), hostname `owlcam`  
**Public watch:** [https://owlcam.tail31318f.ts.net/](https://owlcam.tail31318f.ts.net/) (Firebase redirect: carver-owlcam web app)

**Context note:** Start a **new chat** and attach this file or paste sections below when continuing work.

---

## What was built this session

### IR illuminator (GPIO23)

| Piece | Location |
|--------|----------|
| Core GPIO + safety timers | [pi/scripts/ir_controller.py](../pi/scripts/ir_controller.py) |
| Loopback daemon (motion + API) | [pi/scripts/ir_server.py](../pi/scripts/ir_server.py) `:8767` |
| systemd unit | [pi/systemd/owlcam-ir.service](../pi/systemd/owlcam-ir.service) |
| Field CLI | `owlcam-test-ir` from [pi/scripts/test_ir.py](../pi/scripts/test_ir.py) |
| Config example | [pi/config/ir.env.example](../pi/config/ir.env.example) → `~/.config/owlcam/ir.env` on Pi |
| Admin proxy (auth + CSRF) | [pi/scripts/admin_server.py](../pi/scripts/admin_server.py) — `GET/POST /admin/api/ir/*` |
| Admin UI | OFF / ON / AUTO radios in [web/app.py](../web/app.py) + [web/static/admin.js](../web/static/admin.js) |
| Docs | [admin-panel.md](admin-panel.md) |

**Architecture (important):** `owlcam-admin` has `PrivateDevices=true` — **GPIO runs only in `owlcam-ir`**, not in admin.

**Behavior:** AUTO = dark (Raleigh sunset + `OWLCAM_IR_SIMULATE_DARK`) + RTSP motion diff → pulse ~20s, max continuous 60s, cooldown 10s. Manual cannot bypass thermal cutoff.

**Hardware (verified in field handoff):** GPIO23 → IRF520 SIG; LM2596 3.0V → IR board; separate grounds per harness.

### GPIO admin panel (13 header pins)

| Piece | Location |
|--------|----------|
| Pin data + callouts | [web/data/gpio_header.json](../web/data/gpio_header.json) — **13 `headerPins`** |
| Wiring diagram image | [web/static/owlcam-gpio-wiring.svg](../web/static/owlcam-gpio-wiring.svg) |
| Human doc | [gpio-header.md](gpio-header.md) |
| UI | Admin → **GPIO & nest hardware** |

### Field trip (added after handoff plan)

| Piece | Location |
|--------|----------|
| Field mode (lower bitrate, USB off) | [pi/scripts/field_mode.py](../pi/scripts/field_mode.py), admin `/admin/api/field-mode` |
| Buddy preflight | `/admin/api/preflight`, `owlcam-field-preflight` CLI |

### Git commits (on `main` through GPIO work)

- `2e7a0e1` — IR service, admin API/UI, tests, install-services
- `91894b0` — first GPIO diagram section
- `5e21800` — 13-pin data-driven map
- `10af842` — wiring SVG + connection callouts

### Deploy state

- **Mac:** `make check` passes; deploy with `OWLCAM_SSH_IDENTITY=~/.ssh/owlcam_pi make pi-deploy` (needs [deploy.env](../deploy.env) / `ANIMAL_ID_API_ORIGIN`).
- **Pi:** `owlcam-ir`, `owlcam-admin`, `owlcam-site` were **active** after deploy; `python3-lgpio` installed; `~/.config/owlcam/ir.env` created from example.
- **GitHub Actions “Deploy Pi”:** runs on push to `main` but **skips** without `TS_OAUTH_CLIENT_ID` + `TS_OAUTH_SECRET`.

---

## Original IR field-test checklist

```bash
systemctl --user stop owlcam-ir   # for raw GPIO tests
owlcam-test-ir on|off|pulse --seconds 10 --log-pi-health
systemctl --user start owlcam-ir
```

Admin: `?` → sign in → **IR illuminator** + **GPIO & nest hardware**.

---

## Buddy’s house — slow or missing stream (diagnosis)

**Viewer path:** Browser → Tailscale Funnel → Pi site + MediaMTX HLS (not LAN `100.x:8888`).

| Symptom | Likely cause |
|---------|----------------|
| Very slow / buffering | **Upload** on buddy Wi‑Fi; ~2.5 Mbps nest + ~2 Mbps USB if both on |
| “Cannot reach the camera” | Pi offline (no saved Wi‑Fi/hotspot), Tailscale down |
| “Camera is resting” | Stream unit down or HLS 404 (no publisher on `/owl`) |
| Wrong feed | `sessionStorage` may have **USB** selected; UVC absent at buddy house |

**Runbook:** [buddy-house-runbook.md](buddy-house-runbook.md)

**On Pi while on buddy network:**

```bash
owlcam-field-preflight
nmcli connection show --active
systemctl --user is-active owlcam-mediamtx owlcam-stream owlcam-stream-usb owlcam-site
curl -fsSL -o /dev/null -w 'HLS %{http_code} %{time_total}s\n' \
  http://127.0.0.1:8888/owl/index.m3u8
~/owlcam/deploy/pi/scripts/publish-feed.sh --status
```

- Local HLS **200** + public slow → upload/Funnel; enable **Field mode** in admin or stop USB stream.
- Local HLS **404** → restart `owlcam-stream`, check `journalctl --user -u owlcam-stream -n 50`.

---

## Key commands cheat sheet

```bash
# Mac
cd ~/github/owlcam && make check
OWLCAM_SSH_IDENTITY=~/.ssh/owlcam_pi make pi-deploy
ssh -i ~/.ssh/owlcam_pi shawn@100.123.8.55

# Pi — services
systemctl --user restart owlcam-site owlcam-admin owlcam-ir owlcam-stream
journalctl --user -u owlcam-ir -n 50 --no-pager
curl -s http://127.0.0.1:8767/api/ir/status | python3 -m json.tool

# Pi — reinstall units after deploy stage
bash ~/owlcam/deploy/pi/scripts/install-services.sh
```

---

## How to continue in a new chat

1. Open new Cursor chat on `~/github/owlcam`.
2. Paste: “Read `docs/gpio-header.md` and IR code under `pi/scripts/ir_*`. Goal: …”
3. Attach this file.
