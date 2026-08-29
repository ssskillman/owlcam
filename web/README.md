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

The page is public, but the video remains private. It requests:

```text
https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

That URL requires an authorized Tailscale client and HTTPS serving on the Pi,
for example by proxying local MediaMTX HLS through Tailscale Serve. Until that
is enabled and reachable, the page displays its offline state.

The static bundle in `public/` is generated and intentionally ignored by Git.

The placeholder gallery media in `static/moments/` is sourced from Wikimedia
Commons. Each gallery card links to its source file and Creative Commons
license. Replace these files and the matching `MOMENTS` metadata in `app.py`
when real OwlCam captures are ready.
