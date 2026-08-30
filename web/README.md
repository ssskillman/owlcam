# Carver OwlCam web demo

FastHTML generates the static page deployed to Firebase Hosting:

```bash
uv sync --frozen
uv run python -m pytest
uv run python build.py
firebase deploy --only hosting --project carver-owlcam-72343
```

Production URL: <https://carver-owlcam-72343.web.app>
About Chris: <https://carver-owlcam-72343.web.app/about>
Owl Moments: <https://carver-owlcam-72343.web.app/moments>

The page and nature-camera video are public. The player requests:

```text
https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

Tailscale Funnel proxies only local MediaMTX HLS and the read-only diagnostics
endpoint; the Pi still has no router port forwarding. Switch exposure with
`pi/scripts/publish-feed.sh --public` or `--private`. When the endpoint is not
reachable, the page displays its offline state and retries automatically.

The static bundle in `public/` is generated and intentionally ignored by Git.

Gallery media lives in `static/moments/`, described by `MOMENTS` in `app.py`.
The nest archive photos were shared in the OwlCam Facebook group; their EXIF
capture dates were stripped, so each `timestamp` records when the photo was
added to this log. Confirm photographer credit with the group before using
them more widely. `mole-delivery.webm` remains licensed Wikimedia Commons
stock, badged as a placeholder, until OwlCam records its own clip.
