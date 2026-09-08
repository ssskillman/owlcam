# OwlCam animal identifier

Python service that identifies wildlife photos with YOLOv8 + BioCLIP.
**Never run this on the nest Pi.** v1 is the Mac; later the gaming PC.
The public page lives on the Pi and POSTs here.

## Install (inference host)

Python 3.11 or 3.12:

```bash
cd animal_identifier
uv sync --extra inference
uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port 8767
```

First start downloads `yolov8n.pt` and BioCLIP weights. Bind loopback only.
Publish with Tailscale Funnel on **this machine**, not the Pi:

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
