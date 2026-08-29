# OwlCam — Cursor Handoff / Ground Truth / Build Plan

> **Purpose:** This is the handoff document for continuing the OwlCam project in Cursor.
>
> Treat this file as the current ground truth. The immediate goal is to create a local Git repository at `~/github/owlcam`, connect it to `https://github.com/ssskillman/owlcam`, mirror the working Raspberry Pi configuration/scripts, and then convert the current manual setup into reproducible code and `systemd` services.
>
> **Important:** The working Raspberry Pi is currently the only place where the live-stream setup exists. Do **not** replace or break the working manual path until it has been captured in Git and re-tested.

---

## 1. Project goal

OwlCam is an edge-camera + remote-AI wildlife monitoring system.

Long-term system:

```text
                                ┌──────────────────────────┐
                                │       Owl nest box       │
                                │  IMX708 Camera Module 3  │
                                └────────────┬─────────────┘
                                             │
                                             ▼
                                  ┌────────────────────┐
                                  │ Raspberry Pi 4 2GB │
                                  │ hostname: owlcam   │
                                  └─────────┬──────────┘
                                            │
               ┌────────────────────────────┼──────────────────────────┐
               │                            │                          │
               ▼                            ▼                          ▼
        Live H.264 stream            Snapshot/event queue        Future Facebook
               │                            │                      Live output
               ▼                            ▼
          MediaMTX                   Store-and-forward
               │                            │
        ┌──────┴──────┐                     │
        │             │                     │
      HLS           RTSP                    ▼
        │             │                 Tailscale
        ▼             ▼                     │
 private browser    local clients            ▼
 viewing                               Home AI computer
                                             │
                                      ┌──────┴──────┐
                                      │             │
                                     YOLO      Vision model
                                      │             │
                                      └──────┬──────┘
                                             ▼
                                        Event database
                                             │
                                             ▼
                                  "What happened last night?"
```

The Raspberry Pi should remain an **edge appliance**:

- camera capture
- H.264 encoding
- private live stream
- image/event capture
- local queue
- resilient upload to home
- graceful behavior when internet/home server is unavailable

The stronger home computer will eventually do:

- owl / animal detection
- species classification
- egg/chick detection
- prey identification
- feeding-event detection
- Parent A vs Parent B re-identification
- event logging
- natural-language questions over the event history

---

# 2. Current known-good hardware

## Raspberry Pi

```text
Model:      Raspberry Pi 4 Model B Rev 1.5
RAM:        2 GB
Hostname:   owlcam
OS arch:    aarch64 / 64-bit Raspberry Pi OS Lite
Kernel:     6.18.34+rpt-rpi-v8
User:       shawn
```

The Pi is intentionally headless.

Do not add a desktop environment.

## Camera

Detected camera:

```text
IMX708
4608x2592 10-bit RGGB
```

Known sensor modes observed:

```text
1536x864  @ ~120 fps
2304x1296 @ ~56 fps
4608x2592 @ ~14 fps
```

Working command:

```bash
rpicam-hello --list-cameras
```

Expected:

```text
Available cameras
-----------------
0 : imx708 ...
```

**Hardware note:** The ribbon cable was initially inserted in the wrong orientation. Reversing it while the Pi was powered off fixed camera detection.

---

# 3. Networking / Tailscale

## Local network

At the original/home location the Pi obtained:

```text
LAN IP: 192.168.86.103
```

This IP is **not authoritative** and can change on another network.

Local names that have worked:

```text
owlcam.local
owlcam.lan
```

Do not build scripts that depend on `192.168.86.103`.

## Tailscale

Tailscale is installed and authenticated on the Pi.

Current Pi Tailscale IPv4:

```text
100.123.8.55
```

Remote SSH is confirmed working:

```bash
ssh shawn@100.123.8.55
```

This worked from the Mac over Tailscale.

Tailscale is the preferred remote transport.

### Security rules

- Do **not** port-forward SSH from the public internet.
- Do **not** expose MediaMTX/HLS directly on the public internet.
- Use Tailscale for management and private viewing.
- Do not commit Tailscale auth state, auth keys, Wi-Fi passwords, GitHub tokens, stream keys, or other secrets.

The buddy should eventually receive access by **sharing only the `owlcam` Tailscale machine**, not by giving access to the entire personal tailnet.

---

# 4. Current installed software on the Pi

Known working components:

```text
rpicam-apps / rpicam-vid
FFmpeg
Tailscale
MediaMTX
```

Observed FFmpeg version:

```text
ffmpeg 7.1.5-0+deb13u1+rpt2
```

MediaMTX was installed manually as an ARM64 standalone binary.

Expected locations:

```text
/usr/local/bin/mediamtx
/etc/mediamtx.yml
```

**Do not commit the MediaMTX binary.**

Instead, record/pin the MediaMTX version and create an install/bootstrap script that downloads the correct ARM64 release.

---

# 5. Current known-good live-stream path

This path is working and must be preserved before refactoring.

## Start MediaMTX

Currently started manually:

```bash
mediamtx /etc/mediamtx.yml
```

MediaMTX provides, by default:

```text
RTSP:   port 8554
HLS:    port 8888
WebRTC: port 8889
```

## Publish camera into MediaMTX

Known-good publisher:

```bash
rpicam-vid \
  -t 0 \
  -n \
  --width 1920 \
  --height 1080 \
  --framerate 30 \
  --inline \
  --codec h264 \
  -o - \
| ffmpeg \
  -f h264 \
  -framerate 30 \
  -i - \
  -c:v copy \
  -fflags +genpts \
  -f rtsp \
  rtsp://127.0.0.1:8554/owl
```

This creates the MediaMTX path:

```text
owl
```

## Private browser viewer

Confirmed working over Tailscale:

```text
http://100.123.8.55:8888/owl
```

Direct HLS playlist:

```text
http://100.123.8.55:8888/owl/index.m3u8
```

Eventually prefer a Tailscale/MagicDNS hostname if reliable, but keep the numeric address documented as the known working endpoint.

---

# 6. LAN / Tailscale VLC test that worked

Before MediaMTX, direct UDP testing was used successfully.

The stable Pi command was:

```bash
rpicam-vid \
  -t 0 \
  -n \
  --width 1920 \
  --height 1080 \
  --framerate 30 \
  --inline \
  --codec h264 \
  -o - \
| ffmpeg \
  -f h264 \
  -framerate 30 \
  -i - \
  -c:v copy \
  -fflags +genpts \
  -muxdelay 0 \
  -f mpegts \
  "udp://DESTINATION_IP:5000?pkt_size=1316"
```

Mac VLC receiver:

```bash
/Applications/VLC.app/Contents/MacOS/VLC \
  --network-caching=500 \
  "udp://@:5000"
```

This worked both:

1. over the LAN, and
2. over Tailscale to the Mac's Tailscale IP.

An earlier raw-H.264/UDP attempt caused VLC timestamp/deadlock/late-frame problems. Do not revert to that broken approach.

---

# 7. Important camera-process design constraint

Do **not** assume two independent `rpicam-*` processes can use the physical camera concurrently.

Once the long-running live publisher owns the camera, a second `rpicam-still` process may conflict.

For automated still capture while streaming, prefer extracting snapshots from the **existing local RTSP stream**:

```text
rpicam-vid
   │
   ▼
MediaMTX / RTSP
   │
   ├── HLS viewer
   │
   └── FFmpeg snapshot extractor
```

Example direction:

```bash
ffmpeg \
  -rtsp_transport tcp \
  -i rtsp://127.0.0.1:8554/owl \
  -vf fps=1/30 \
  /home/shawn/owlcam/outbox/%Y-%m-%dT%H-%M-%S.jpg
```

Do not blindly use this exact command in production without verifying timestamp expansion and file overwrite behavior. Implement a robust snapshot script instead.

---

# 8. GitHub / local repo objective

The user supplied this repository:

```text
https://github.com/ssskillman/owlcam
```

The desired local path is:

```text
~/github/owlcam
```

**Use `owlcam` with no space.**

## Preferred bootstrap on the Mac

First verify GitHub CLI auth:

```bash
gh auth status
```

Then:

```bash
mkdir -p ~/github
cd ~/github
gh repo clone ssskillman/owlcam owlcam
cd ~/github/owlcam
```

Alternative SSH clone:

```bash
git clone git@github.com:ssskillman/owlcam.git ~/github/owlcam
```

If the repository exists but is private, authenticate GitHub first.

If it has not actually been initialized remotely, do **not** silently create a different repository. Confirm the remote repo and then initialize locally:

```bash
mkdir -p ~/github/owlcam
cd ~/github/owlcam
git init
git branch -M main
git remote add origin git@github.com:ssskillman/owlcam.git
```

Verify:

```bash
git remote -v
git status
```

---

# 9. FIRST CURSOR TASK: mirror the working Pi before adding features

Cursor should first capture the current state from the working Pi.

From the local repo:

```bash
mkdir -p \
  pi/config \
  pi/scripts \
  pi/systemd \
  docs \
  home-ai \
  tests
```

Suggested repo:

```text
owlcam/
├── README.md
├── CURSOR_HANDOFF_OWLCAM.md
├── .gitignore
├── .env.example
├── Makefile
│
├── docs/
│   ├── architecture.md
│   ├── buddy-house-runbook.md
│   ├── recovery.md
│   └── security.md
│
├── pi/
│   ├── config/
│   │   └── mediamtx.yml
│   │
│   ├── scripts/
│   │   ├── install.sh
│   │   ├── start-stream.sh
│   │   ├── capture-snapshot.py
│   │   ├── uploader.py
│   │   ├── healthcheck.sh
│   │   └── deploy.sh
│   │
│   └── systemd/
│       ├── owlcam-mediamtx.service
│       ├── owlcam-stream.service
│       ├── owlcam-capture.service
│       └── owlcam-uploader.service
│
├── home-ai/
│   ├── README.md
│   └── app/
│
└── tests/
```

## Pull current MediaMTX config

From the Mac/local repo:

```bash
ssh shawn@100.123.8.55 'sudo cat /etc/mediamtx.yml' \
  > pi/config/mediamtx.yml
```

Before committing, inspect it for credentials/secrets:

```bash
grep -nEi 'password|token|secret|key|user' pi/config/mediamtx.yml
```

Do not commit anything sensitive.

## Inventory the Pi

Capture these outputs into documentation, **not secrets**:

```bash
ssh shawn@100.123.8.55 '
set -x
hostname
cat /proc/device-tree/model; echo
uname -a
cat /etc/os-release
hostname -I
tailscale ip -4
which rpicam-vid
which ffmpeg
which mediamtx
ffmpeg -version | head -1
mediamtx --version
rpicam-hello --list-cameras
'
```

Also inspect current services:

```bash
ssh shawn@100.123.8.55 \
  "systemctl list-unit-files | grep -Ei 'tailscale|mediamtx|owlcam' || true"
```

Do not pull `/var/lib/tailscale` or any Tailscale machine state into Git.

---

# 10. Repository should become the source of truth

Current state:

```text
Pi = source of truth
Git = not yet source of truth
```

Target:

```text
GitHub repo
    │
    ▼
local repo
    │
    ▼
deploy/install
    │
    ▼
Pi
```

After initial mirroring, manual edits directly on the Pi should be avoided.

Desired workflow:

```text
edit locally
→ test/lint
→ commit
→ push GitHub
→ deploy to Pi over Tailscale
→ verify
```

A first deployment script can use `rsync` over SSH:

```bash
rsync -av \
  --exclude '.git' \
  pi/scripts/ \
  shawn@100.123.8.55:/home/shawn/owlcam/scripts/
```

For system files, deploy to a temporary location first and install with `sudo` on the Pi.

Never make `rsync --delete /`-style broad deployments.

---

# 11. Phase plan

## Phase 0 — preserve current working system

**Goal:** Git contains everything needed to reproduce the manually working stream.

Deliverables:

- current MediaMTX config mirrored
- known-good publisher script
- Pi inventory
- install script
- GitHub remote configured
- README with known-good commands

Success:

```text
fresh shell
→ repo scripts
→ MediaMTX starts
→ camera publishes
→ browser opens live stream
```

---

## Phase 1 — automatic/reliable Pi services

Replace manual terminal sessions with `systemd`.

### A. MediaMTX service

Create:

```text
owlcam-mediamtx.service
```

Requirements:

- starts at boot
- uses `/etc/mediamtx.yml`
- restarts on failure
- logs to journal
- no dependency on internet access

### B. Camera publisher service

Create:

```text
owlcam-stream.service
```

Requirements:

- starts after MediaMTX
- runs known-good `rpicam-vid | ffmpeg` pipeline
- `Restart=always`
- `RestartSec=5`
- survives SSH disconnect
- publishes `rtsp://127.0.0.1:8554/owl`

### C. Snapshot capture

Create:

```text
owlcam-capture.service
```

Requirements:

- captures from the existing RTSP feed, not a second physical-camera process
- writes atomically into:

```text
/home/shawn/owlcam/outbox/
```

- configurable cadence
- filenames include UTC timestamp + unique identifier
- camera/network errors do not kill the service permanently

Suggested folders:

```text
/home/shawn/owlcam/
├── outbox/
├── sent/
├── failed/
├── logs/
└── scripts/
```

### D. Store-and-forward uploader

Create:

```text
owlcam-uploader.service
```

Required behavior:

```text
capture
   ↓
outbox
   ↓
try home AI API
   │
   ├── success → mark/move sent
   │
   └── failure → leave in outbox
                    ↓
                 retry later
```

Uploader requirements:

- oldest-first
- connection timeout
- exponential backoff
- does not crash when:
  - Wi-Fi is down
  - Tailscale is down
  - home PC is off
  - API is unavailable
- avoids duplicate processing using a capture/event ID
- limits disk usage
- deletes old **sent** files before unsent files
- logs queue depth and last successful upload

Do not couple capture to upload.

---

# 12. systemd conventions

Suggested unit style:

```ini
[Unit]
Description=OwlCam <component>
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=shawn
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Adjust dependency ordering appropriately.

For the stream:

```text
owlcam-stream
    ↓ requires/after
owlcam-mediamtx
```

For capture:

```text
owlcam-capture
    ↓ uses
local RTSP /owl
```

The uploader may start without connectivity. It must simply wait/retry.

---

# 13. Secrets/configuration

Create:

```text
.env.example
```

Example only:

```dotenv
OWLCAM_RTSP_URL=rtsp://127.0.0.1:8554/owl
OWLCAM_HLS_PORT=8888
OWLCAM_PATH=owl
OWLCAM_CAPTURE_INTERVAL_SECONDS=30
OWLCAM_HOME_AI_URL=http://HOME_AI_TAILSCALE_HOST:8000/analyze
OWLCAM_OUTBOX=/home/shawn/owlcam/outbox
OWLCAM_SENT=/home/shawn/owlcam/sent
OWLCAM_MAX_DISK_PERCENT=70
```

Real secrets/config overrides belong outside Git, e.g.:

```text
/etc/owlcam/owlcam.env
```

`.gitignore` should include at least:

```gitignore
.env
*.secret
*.key
captures/
outbox/
sent/
failed/
__pycache__/
.venv/
.DS_Store
```

Never commit:

- Wi-Fi passwords
- Tailscale auth keys/state
- Facebook stream keys
- GitHub tokens
- private SSH keys

---

# 14. Buddy's house runbook — NO ETHERNET REQUIRED

This must become `docs/buddy-house-runbook.md`.

## Before leaving home

The Pi should know at least:

1. home Wi-Fi
2. the user's phone hotspot

The phone hotspot is the rescue path.

Verify Tailscale:

```bash
ssh shawn@100.123.8.55
tailscale status
```

Verify automatic services once implemented:

```bash
sudo systemctl status \
  owlcam-mediamtx \
  owlcam-stream \
  owlcam-capture \
  owlcam-uploader
```

### Preload phone hotspot

From the Pi while still at home:

```bash
sudo nmcli dev wifi connect "PHONE_HOTSPOT_SSID" \
  password "PHONE_HOTSPOT_PASSWORD"
```

Then reconnect to home Wi-Fi if necessary.

Ensure the hotspot profile remains configured:

```bash
nmcli connection show
```

Do **not** put either credential in Git.

---

## Arrival at buddy's house

### Step 1 — temporary internet

Turn on the known phone hotspot.

Power OwlCam.

Wait ~60–120 seconds.

The Pi should join the known hotspot and Tailscale should come online.

### Step 2 — SSH over Tailscale

From the Mac:

```bash
ssh shawn@100.123.8.55
```

If this works, the physical location and local subnet no longer matter.

### Step 3 — scan buddy Wi-Fi

On the Pi:

```bash
nmcli dev wifi rescan
nmcli dev wifi list
```

### Step 4 — connect to buddy Wi-Fi

```bash
sudo nmcli dev wifi connect "BUDDYS_WIFI_SSID" \
  password "BUDDYS_WIFI_PASSWORD"
```

The SSH connection may drop when the Wi-Fi interface switches.

That is expected.

### Step 5 — reconnect

Wait 10–30 seconds:

```bash
ssh shawn@100.123.8.55
```

Tailscale should use the buddy's internet connection and retain the same OwlCam Tailscale address.

### Step 6 — verify

On Pi:

```bash
hostname
hostname -I
tailscale ip -4
tailscale status
nmcli connection show --active
rpicam-hello --list-cameras
```

Expected Tailscale IP:

```text
100.123.8.55
```

### Step 7 — verify services

Once systemd automation exists:

```bash
sudo systemctl --no-pager --full status \
  owlcam-mediamtx \
  owlcam-stream \
  owlcam-capture \
  owlcam-uploader
```

If necessary:

```bash
sudo systemctl restart \
  owlcam-mediamtx \
  owlcam-stream \
  owlcam-capture \
  owlcam-uploader
```

### Step 8 — view remotely

From an authorized Tailscale device:

```text
http://100.123.8.55:8888/owl
```

Direct HLS:

```text
http://100.123.8.55:8888/owl/index.m3u8
```

---

# 15. Buddy viewer access

Do **not** give the buddy the `shawn` Pi account merely to watch video.

Preferred design:

1. Share only the `owlcam` machine using Tailscale's machine-sharing feature.
2. Buddy installs Tailscale and signs into their own account.
3. Buddy accepts the shared machine.
4. Buddy opens the HLS viewer.

Known viewer:

```text
http://100.123.8.55:8888/owl
```

Later add viewer authentication if desired.

Do not grant SSH unless there is a specific administrative reason.

---

# 16. Failure / recovery behavior

The system must be designed so these conditions are normal, not fatal:

```text
buddy Wi-Fi unavailable
internet unavailable
Tailscale temporarily disconnected
home AI PC powered off
home AI API unavailable
GitHub unavailable
viewer disconnected
```

Expected behavior:

```text
Live local camera process: keeps running
MediaMTX:                  keeps running
Capture:                   keeps creating queued images if possible
Uploader:                  waits/retries
Queue:                     persists across reboot
Home server returns:       backlog drains automatically
```

A network outage must **not** crash the camera stack.

---

# 17. Home AI server — planned, NOT implemented yet

Do not pretend this exists yet.

Planned home endpoint:

```text
POST /analyze
```

Possible response:

```json
{
  "capture_id": "2026-08-29T02:14:31Z-abc123",
  "owl_present": true,
  "species": "Barred Owl",
  "species_confidence": 0.94,
  "adult_count": 1,
  "chick_count": 3,
  "egg_count": 0,
  "prey_present": true,
  "prey_type": "mouse",
  "prey_confidence": 0.89,
  "feeding_event": true,
  "individual": "unknown"
}
```

Planned model split:

```text
fast detector (YOLO or similar)
        ↓
interesting image?
        ↓ yes
vision-language / classifier
        ↓
structured result
```

Future individual owl re-identification should use a dedicated re-ID / embedding approach with:

```text
Parent A
Parent B
Unknown
```

Do not force an identity when confidence is low.

Future prey categories:

```text
mouse
rat
rabbit
snake
fish
frog
bird
insect
unknown
```

Future lifecycle state:

```text
eggs
pipping suspected
hatched
chicks
```

---

# 18. Event history / future query layer

Long-term OwlCam should store structured events rather than only image descriptions.

Example:

```text
2026-08-28 21:14 Parent A arrived
2026-08-28 21:16 feeding event — mouse — 94%
2026-08-28 23:03 Parent B arrived
2026-08-28 23:04 feeding event — probable snake — 88%
2026-08-29 01:31 three chicks visible
```

This enables queries such as:

```text
"What happened last night?"
"How many feeding visits happened this week?"
"What prey did Parent B bring?"
"When was the last time all chicks were visible?"
"Show me the best image from every feeding event."
```

SQLite is sufficient for the first implementation.

Do not introduce a vector database until there is a demonstrated need.

---

# 19. Facebook Live — future phase

Facebook Live is **not configured yet**.

Do not store Facebook stream keys in Git.

Eventually:

```text
Camera
   ↓
rpicam-vid
   ↓
FFmpeg
   ├── MediaMTX/private view
   └── Facebook RTMPS
```

First priority is a reliable private/offline-safe system.

---

# 20. Infrared / enclosure notes

IR lighting is a hardware phase.

Do not power unknown IR illuminators directly from GPIO without verifying voltage/current requirements.

The camera is an IMX708 Camera Module 3-family device. Confirm whether it is standard or NoIR before assuming IR illumination performance.

Outdoor enclosure plan:

- IP65 minimum; IP67 preferred
- Pi/electronics in weatherproof enclosure
- cable glands on bottom
- ventilation/condensation strategy
- keep IR illumination optically isolated from the camera window to avoid IR reflection/haze

No software should assume the IR hardware is already controllable.

---

# 21. Cursor implementation rules

Cursor should follow these rules:

1. **Preserve known-good behavior first.**
2. Mirror the Pi's current configuration before refactoring.
3. Git becomes the source of truth.
4. Do not put secrets in Git.
5. Use Tailscale for remote management.
6. Do not require a fixed LAN IP.
7. Do not expose router ports.
8. Services must restart automatically.
9. Network failure must be handled as an expected state.
10. Capture and upload are independent processes.
11. Prefer small, reviewable commits.
12. Add shell `set -euo pipefail` where appropriate.
13. Python services should use structured logging and explicit exception handling.
14. Add timeouts to all outbound HTTP requests.
15. Make upload idempotent with a stable capture ID.
16. Do not delete unsent data merely because the server is unreachable.
17. Do not run a second physical camera process merely to take stills while streaming.
18. Document every command required for a clean rebuild.
19. Provide `--dry-run` or safe verification modes for deployment scripts where practical.
20. Before changing a working stream command, benchmark/test the replacement.

---

# 22. Suggested first commits

Keep the commits understandable.

### Commit 1

```text
docs: capture current OwlCam working state
```

Contains:

- this handoff
- architecture
- known-good commands
- Pi inventory
- buddy-house runbook

### Commit 2

```text
chore: add Pi bootstrap and MediaMTX config
```

Contains:

- install script
- MediaMTX config
- version pinning
- `.gitignore`
- `.env.example`

### Commit 3

```text
feat: run MediaMTX and camera publisher with systemd
```

Success test:

```bash
sudo reboot
```

Then, without SSH starting anything manually:

```text
http://100.123.8.55:8888/owl
```

must work.

### Commit 4

```text
feat: add offline-safe snapshot capture queue
```

### Commit 5

```text
feat: add resilient store-and-forward uploader
```

---

# 23. Definition of "Phase 1 done"

Phase 1 is complete only when this works:

```text
1. Reboot Pi.
2. Do not SSH in to manually start anything.
3. Camera becomes available.
4. MediaMTX starts.
5. /owl stream starts.
6. HLS viewer works over Tailscale.
7. Snapshots appear in outbox.
8. Turn home AI endpoint off.
9. Capture keeps running.
10. Queue grows without crashing.
11. Turn home AI endpoint on.
12. Queue drains automatically.
13. Reboot during an outage.
14. Queue survives reboot.
15. Restore connectivity.
16. Upload resumes.
```

---

# 24. Immediate next action for Cursor

**Do not begin with AI.**

Perform these actions in order:

```text
1. Clone/initialize ~/github/owlcam.
2. Save this handoff into the repo.
3. Inventory the live Pi over 100.123.8.55.
4. Pull /etc/mediamtx.yml into the repo after secret review.
5. Create README + repo structure.
6. Create a known-good start-stream.sh matching the exact working command.
7. Create install/deploy scripts.
8. Commit and push the mirrored baseline.
9. Only then build systemd automation.
10. Only after streaming survives reboot build capture + uploader.
```

At each stage, verify the current HLS viewer still works:

```text
http://100.123.8.55:8888/owl
```

---

# 25. Useful current commands

SSH:

```bash
ssh shawn@100.123.8.55
```

Camera detection:

```bash
rpicam-hello --list-cameras
```

Pi identity:

```bash
hostname
cat /proc/device-tree/model; echo
hostname -I
tailscale ip -4
```

Network:

```bash
nmcli dev wifi list
nmcli connection show
nmcli connection show --active
```

MediaMTX:

```bash
mediamtx /etc/mediamtx.yml
```

Private stream:

```text
http://100.123.8.55:8888/owl
```

Logs once services exist:

```bash
journalctl -u owlcam-mediamtx -f
journalctl -u owlcam-stream -f
journalctl -u owlcam-capture -f
journalctl -u owlcam-uploader -f
```

---

# 26. What is still needed

Before declaring OwlCam field-ready, the project still needs:

- [ ] local Git repo connected to personal GitHub
- [ ] current Pi state mirrored into Git
- [ ] reproducible Pi bootstrap/install script
- [ ] MediaMTX systemd service
- [ ] camera publisher systemd service
- [ ] automatic boot verification
- [ ] phone-hotspot fallback profile verified
- [ ] buddy-house Wi-Fi field test
- [ ] offline snapshot queue
- [ ] uploader retry/backoff
- [ ] disk-space guardrails
- [ ] home AI receiver
- [ ] event database
- [ ] viewer sharing test with buddy
- [ ] IR hardware validation
- [ ] outdoor enclosure/weatherproofing
- [ ] Facebook Live output
- [ ] monitoring/health endpoint

The first priority is **reproducibility and resilience**, not additional AI features.

---

# 27. North-star behavior

Eventually installation at the buddy's house should be:

```text
mount OwlCam
↓
turn on power
↓
Pi joins known Wi-Fi
↓
Tailscale reconnects
↓
MediaMTX starts automatically
↓
camera stream starts automatically
↓
capture queue starts automatically
↓
uploads go home when reachable
↓
open browser
↓
OWL CAM LIVE
```

No monitor.

No keyboard.

No SSH required for normal startup.

No crash because home internet or the AI computer is temporarily unavailable.

That is the standard the repo should build toward.

---

**End of handoff.**
