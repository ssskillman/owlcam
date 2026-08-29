# Security

## Trust boundaries and assets

OwlCam crosses three boundaries: the site Wi-Fi network, the private Tailscale
network, and GitHub. Assets include SSH access, Wi-Fi credentials, Tailscale
identity, future upload credentials, camera footage, and future stream keys.

## Required controls

- Use Tailscale for SSH and private viewing.
- Do not forward SSH, RTSP, HLS, or WebRTC ports on the router.
- Share only the `owlcam` Tailscale machine with viewers.
- Leave Tailscale Funnel off. It publishes port 443 with no authentication and
  no rate limit. To reach viewers who are not on the tailnet, restream outbound
  or publish clips, rather than opening inbound. See
  [`live-feed.md`](live-feed.md).
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
