# OwlCam animal identifier

Python service that identifies wildlife photos with YOLOv8 + BioCLIP.
**Never run this on the nest Pi.** v1 is the Mac; the long-term host is the
gaming PC. The public page lives on the Pi and POSTs here.

## Install (inference host)

Python 3.11 or 3.12:

```bash
cd animal_identifier
uv sync --extra inference
uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
```

On the **Windows gaming PC**, Torch must stay the CUDA build (`+cu130` on the
RTX 5070). Do **not** run a plain `uv lock` from this repo's PyPI pin — that
replaces CUDA Torch with CPU Torch. Keep the existing `.venv` after `git pull`.

First start downloads `yolov8n.pt` and BioCLIP weights. Bind loopback only.
YOLO and BioCLIP use CUDA when `torch.cuda.is_available()`.

### Prove one image on the gaming PC (before Funnel)

```powershell
uv run python -c "import torch; assert torch.cuda.is_available() and '+cu' in torch.__version__; print(torch.__version__, torch.cuda.get_device_name(0))"
uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
```

In another PowerShell: `nvidia-smi -l 1`

```powershell
curl.exe -X POST "http://127.0.0.1:8767/api/animal-identification" -F "images=@C:\Users\sskil\Pictures\owl.jpg"
```

Swagger `/docs` should show a file picker for Identify. If you still see
`array<string>`, hard-refresh; curl remains the reliable check.

Publish with Tailscale Funnel on **this machine**, not the Pi, **after** that
POST returns JSON and `nvidia-smi` shows the RTX 5070 in use:

```bash
tailscale funnel --bg --https=443 http://127.0.0.1:8767
```

Then set `ANIMAL_ID_API_ORIGIN` to this host's `https://<name>.tail31318f.ts.net`
when building the site, and `OWLCAM_ANIMAL_ID_ORIGIN` on the Pi site unit so
CSP can `connect-src` / `img-src` that origin.

macOS keepalive: copy `launchd/com.owlcam.animal-id.plist.example` to
`~/Library/LaunchAgents/`, replace `REPLACE` with your home path, then
`launchctl load` it. Funnel still has to be started on that Mac.

Moving to the gaming PC: [`docs/next-steps/animal-id-inference-host.md`](../docs/next-steps/animal-id-inference-host.md).

## Tests (no GPU, no weight download)

```bash
cd animal_identifier
uv sync --group dev
uv run pytest
```
