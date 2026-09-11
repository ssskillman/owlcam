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

Do **not** point Funnel at random ports yet. Wait until a local image POST
classifies on the RTX 5070 (`nvidia-smi` shows Python using the GPU).

### Prove local GPU inference (do this before Funnel)

The PC already has Python 3.12, `uv`, and CUDA Torch (`2.14.0+cu130`).
Keep that `.venv`. After pulling this repo:

```powershell
cd C:\Users\sskil\github\owlcam
git pull
cd animal_identifier
uv run python -c "import torch; assert torch.cuda.is_available() and '+cu' in torch.__version__; print(torch.__version__, torch.cuda.get_device_name(0))"
uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
```

Do **not** run `uv lock` or a fresh `uv sync --extra inference` against
PyPI — the git lockfile is CPU Torch and would wipe `+cu130`.

Other PowerShell: `nvidia-smi -l 1`

```powershell
curl.exe -X POST "http://127.0.0.1:8767/api/animal-identification" -F "images=@C:\Users\sskil\Pictures\owl.jpg"
```

First POST may download YOLO and BioCLIP weights. Success is JSON
`results` plus GPU memory/util on the RTX 5070.

## Cutover (when the service is in the repo)

On the **gaming PC**:

1. Clone `https://github.com/ssskillman/owlcam` (or pull `main`).
2. Start (skip `uv sync` if CUDA Torch is already installed):

   ```bash
   cd animal_identifier
   uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
   ```

   First run downloads YOLO and BioCLIP weights.
3. Funnel **8443** on this PC (not 443 — that is the Pi site, and the
   Identify origin is `:8443`):

   ```bash
   tailscale funnel --bg --yes --https=8443 http://127.0.0.1:8767
   ```

4. Note this PC’s origin, e.g.
   `https://<pc-name>.tail31318f.ts.net:8443`.
5. If you want “Looks right / Not quite” history and the animals-identified
   chart, copy `feedback.sqlite` and `identifications.sqlite` from
   `~/.owlcam/animal-id/` on the Mac to the same path here. The chart
   otherwise starts at zero.

On the **Mac / laptop that deploys the site**:

1. Point `ANIMAL_ID_API_ORIGIN` at the **PC** MagicDNS origin (no
   trailing slash) in `deploy.env`, which is gitignored and read by the
   Makefile, then rebuild:

   ```bash
   # deploy.env — see deploy.env.example
   ANIMAL_ID_API_ORIGIN=https://<pc-name>.tail31318f.ts.net:8443
   ```

   ```bash
   make pi-deploy
   ```

   A file rather than an `export` because the value has to survive a new
   shell: `make pi-deploy` without it rebuilds `/identify` with an empty
   origin, and the page then reports the photo-processing server as
   offline while the build and the deploy both look fine. `pi-deploy`
   refuses to run when it is unset.

2. On the Pi, put the **same** origin, including `:8443`, in
   `~/.config/owlcam/site.env`:

   ```bash
   OWLCAM_ANIMAL_ID_ORIGIN=https://<pc-name>.tail31318f.ts.net:8443
   ```

   then `systemctl --user restart owlcam-site.service` so CSP allows
   `connect-src` / `img-src` for that host. Dropping the port makes the
   page load and the uploads fail.
3. On the Mac, stop uvicorn and drop its `:8443` publish so there is
   only one identifier:

   ```bash
   tailscale funnel --https=8443 off
   tailscale serve --https=8443 off
   ```

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
