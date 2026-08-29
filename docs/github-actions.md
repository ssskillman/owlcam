# GitHub Actions

The repository remote is `https://github.com/ssskillman/owlcam`.

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs `make check` on
pull requests and on pushes to `main`.

## Deploy Pi

[`.github/workflows/deploy-pi.yml`](../.github/workflows/deploy-pi.yml) joins
the tailnet with the official Tailscale GitHub Action, then rsyncs scripts to
`/home/shawn/owlcam/deploy` over SSH. Port 22 is never exposed on the public
internet.

Source: [tailscale/github-action](https://github.com/tailscale/github-action)

If the Pi is powered off or Tailscale is down, the workflow **does not fail**.
It logs that the Pi is offline, emits an Actions notice, skips staging, and
finishes green. Re-run **Deploy Pi** when the device is back.

Installing `/etc/mediamtx.yml` still requires a manual `workflow_dispatch` with
**install_config** enabled.

### One-time GitHub secrets

Create these repository secrets:

| Secret | Purpose |
| --- | --- |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client with writable `auth_keys` |
| `TS_OAUTH_SECRET` | Matching OAuth client secret |
| `OWLCAM_SSH_KEY` | Private key whose public half is in `shawn`'s `authorized_keys` on the Pi |

Optional repository variable:

| Variable | Purpose |
| --- | --- |
| `OWLCAM_SSH_TARGET` | Defaults to `shawn@100.123.8.55` |

### Tailscale admin

1. Create tag `tag:ci`.
2. Create an OAuth client with writable `auth_keys` scoped to `tag:ci`.
3. Allow `tag:ci` to reach the OwlCam machine on TCP 22 (ACL).
4. Add the deploy public key on the Pi. Do not commit the private key.

Until those secrets exist, the deploy job is skipped entirely.
