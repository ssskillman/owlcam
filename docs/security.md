# Security

## Trust boundaries and assets

OwlCam crosses three boundaries: the site Wi-Fi network, the private Tailscale
network, and GitHub. Assets include SSH access, Wi-Fi credentials, Tailscale
identity, future upload credentials, camera footage, and future stream keys.

## Required controls

- Use Tailscale for SSH and private viewing.
- Do not forward SSH, RTSP, HLS, or WebRTC ports on the router.
- Share only the `owlcam` Tailscale machine with viewers.
- Funnel is the **intended** exposure so anyone can watch without a tailnet
  account, pending one-time approval of the `funnel` node attribute.
  It publishes port 443 with no network-level authentication or rate limit, so
  it must keep proxying only the built site, MediaMTX HLS, read-only diagnostics,
  and the narrowly authenticated admin API. Never expose RTSP, SSH, an arbitrary
  command runner, or the filesystem. Revert with
  `pi/scripts/publish-feed.sh --private`. The admin exception uses fixed
  allowlisted operations, a scrypt password hash, server-side expiring sessions,
  Secure/HttpOnly/SameSite cookies, CSRF and same-origin write checks, bounded
  logs, and login throttling. See [`admin-panel.md`](admin-panel.md).
- The site mount is read-only by construction: `site_server.py` serves `GET` and
  `HEAD` only, refuses any path that resolves outside the site root, and binds
  to loopback so Tailscale is the only way in. It also sends the CSP,
  `Referrer-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, and
  `Permissions-Policy` headers that `firebase.json` used to apply — they moved
  with the page, so changing one file no longer silently drops them.
- Treat the diagnostics payload as public. It is an allowlist of temperature,
  memory, load, process booleans, and nest climate; adding PIDs, paths,
  usernames, or IP addresses to it would publish them to the internet.
- Keep `~/.config/owlcam/admin.env` mode `600`. It contains a password hash, not
  plaintext, but still enables offline password guessing if copied. Never stage
  it through repository deployment.
- Keep runtime configuration under `/etc/owlcam`, readable only as required.
- Review MediaMTX authentication settings before every configuration commit.
- Download MediaMTX over HTTPS and verify the release checksum before install.
- Stage deployment files under `/home/shawn/owlcam/deploy`; require an explicit
  flag before replacing `/etc/mediamtx.yml`.
- GitHub deploy uses Tailscale plus a dedicated SSH key in repository secrets.
  Never commit Tailscale OAuth credentials or the deploy private key.

## Never commit

- Wi-Fi or hotspot passwords
- Tailscale auth keys or `/var/lib/tailscale`
- GitHub tokens or SSH private keys
- Facebook stream keys
- Future home-AI credentials
- Captures, outbox contents, or event payloads containing private data

Use [`.env.example`](../.env.example) only as a placeholder template. Real
values belong in `/etc/owlcam/owlcam.env`.

## Pre-commit review

```bash
git diff --cached --check
git diff --cached | \
  grep -nEi 'password|token|secret|api[_-]?key|private[_-]?key'
git ls-files | \
  grep -Ei '(^|/)(\.env|outbox|sent|failed|captures)(/|$)|\.(key|pem)$'
```

Matches in documentation and placeholder names require human review; they are
not automatically secrets. If a real credential reaches GitHub, revoke and
replace it immediately rather than relying only on history rewriting.
