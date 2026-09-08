# Move animal ID off the Mac onto the gaming PC

The public **Identify** page stays on the nest Pi. YOLO + BioCLIP never
run on the Pi. v1 of the API is the Mac; **this box is the long-term
host** (Windows + NVIDIA is expected). Same app in git — not a second
codebase.

Identify is **offline whenever this PC is off**, same as the Mac. Live
video does not depend on it.

Do this **after** `animal_identifier/` is on `main` (it is in the repo now).
Until the PC is the live host, skip to “While you wait.”

## While you wait (PC prep)

1. Install [Tailscale](https://tailscale.com/download) on the gaming PC.
   Sign in to the **same tailnet** as `owlcam` (`tail31318f`).
2. In the Tailscale admin console, grant this node the **funnel**
   attribute (same as the Pi). Funnel is what lets phones without
   Tailscale reach the API.
3. Install a current **Python 3.11 or 3.12** (64-bit).
4. Optional but recommended: NVIDIA drivers + CUDA-capable
   **PyTorch** (`pip` index from pytorch.org). CPU works; GPU is faster.
5. Leave disk space for Hugging Face / Ultralytics caches (BioCLIP +
   `yolov8n.pt`, on the order of a few GB).

Do **not** point Funnel at random ports yet. Wait for the repo’s run
script and port.

## Cutover (when the service is in the repo)

On the **gaming PC**:

1. Clone `https://github.com/ssskillman/owlcam` (or pull `main`).
2. Install and start:

   ```bash
   cd animal_identifier
   uv sync --extra inference
   uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
   ```

   First run downloads YOLO and BioCLIP weights.
3. Funnel **only** that port on this PC:

   ```bash
   tailscale funnel --bg --https=443 http://127.0.0.1:8767
   ```

4. Note this PC’s MagicDNS name, e.g.
   `https://<pc-name>.tail31318f.ts.net`.
5. If you want “Looks right / Not quite” history, copy
   `~/.owlcam/animal-id/feedback.sqlite` from the Mac to the same path here.

On the **Mac / laptop that deploys the site**:

1. Set `ANIMAL_ID_API_ORIGIN` to the **PC** Funnel/MagicDNS origin
   (no trailing slash) and rebuild:

   ```bash
   export ANIMAL_ID_API_ORIGIN='https://<pc-name>.tail31318f.ts.net'
   make pi-deploy
   ```

2. On the Pi, put the same origin in `~/.config/owlcam/site.env`:

   ```bash
   OWLCAM_ANIMAL_ID_ORIGIN=https://<pc-name>.tail31318f.ts.net
   ```

   then `systemctl --user restart owlcam-site.service` so CSP allows
   `connect-src` / `img-src` for that host.
3. Turn **off** Funnel (or the API process) on the Mac so you do not
   have two identifiers.

## Prove it

- PC on: Identify on
  `https://owlcam.tail31318f.ts.net/identify` returns a result.
- PC off: page loads, copy says the identifier is offline; **live feed
  still plays**.
- A phone **without** Tailscale can still identify (Funnel on the PC).
- A device **with** Tailscale can still identify (MagicDNS to the PC’s
  `100.x` is OK: page is the Pi, API is the PC — both tailnet, not
  “public page → Pi private IP” the way Firebase + `*.ts.net` broke
  video).
- Nest cam `/owl` still 200 the whole time.

## Do not

- Install torch / YOLO on the Raspberry Pi.
- Funnel the identifier through the Pi (`publish-feed.sh` stays site,
  `/owl`, diagnostics, admin).
- Hard-code the Mac hostname in JS; one env/origin for all hosts.
- Train on visitor photos unless they opted in.

## Related

- Handoff spec: `OWLCAM_COMMUNITY_ANIMAL_ID_HANDOFF.md` (Downloads).
- Streamlit prototype: `owlcam-still-image-demo` (local only).
- Always-up site + camera #2 (separate, waiting on a public domain):
  [`always-up-and-camera-2.md`](always-up-and-camera-2.md)
