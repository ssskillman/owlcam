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

The page is public, but the video remains private. It requests:

```text
https://owlcam.tail31318f.ts.net/owl/index.m3u8
```

That URL requires an authorized Tailscale client and HTTPS serving on the Pi,
for example by proxying local MediaMTX HLS through Tailscale Serve. Until that
is enabled and reachable, the page displays its offline state.

The static bundle in `public/` is generated and intentionally ignored by Git.
