# Carver OwlCam web demo

FastHTML generates the static page, which the Pi serves beside the stream:

```bash
uv sync --frozen
uv run python -m pytest
uv run python build.py
make pi-deploy          # from the repo root: builds and stages the site to the Pi
```

Link to share: <https://carver-owlcam-72343.web.app>
About Chris: <https://carver-owlcam-72343.web.app/about>
Owl Moments: <https://carver-owlcam-72343.web.app/moments>

Those 302 to the Pi with the path preserved, so the address bar ends on
<https://owlcam.tail31318f.ts.net/> — the origin that actually serves the page.
Prefer the Firebase links when sharing: the redirect is repointable, so a hostname
change never invalidates a link someone already has. `make deploy` publishes
those redirects; `make pi-deploy` publishes the page itself.

The page and nature-camera video are public, and both come from the same origin
so the player can request relative paths:

```text
/owl/index.m3u8
/diagnostics
```

That is load-bearing, not cosmetic. Hosting the page on a different origin made
the video unplayable on every device running Tailscale, because a public page is
not permitted to reach the private address MagicDNS returns. See
[`../docs/live-feed.md`](../docs/live-feed.md).

Tailscale Funnel proxies only the built site, MediaMTX HLS, and the read-only
diagnostics endpoint; the Pi still has no router port forwarding. Switch exposure
with `pi/scripts/publish-feed.sh --public` or `--private`. When the stream is not
reachable, the page names the failure it hit and retries automatically.

Because the Pi serves the page, `pi/scripts/site_server.py` sends the security
headers Firebase used to add, and `web/tests` no longer asserts them from
`firebase.json`.

The static bundle in `public/` is generated and intentionally ignored by Git.

Gallery media lives in `static/moments/`, described by `MOMENTS` in `app.py`.
The nest archive photos were shared in the OwlCam Facebook group; their EXIF
capture dates were stripped, so each `timestamp` records when the photo was
added to this log. Confirm photographer credit with the group before using
them more widely. `mole-delivery.webm` remains licensed Wikimedia Commons
stock, badged as a placeholder, until OwlCam records its own clip.
