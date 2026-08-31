# OwlCam admin panel

Click the `?` in the site navigation to open the admin login. The panel is
available on every page and works on mobile.

After authentication, an administrator can:

- start or stop `owlcam-stream.service` without taking the site offline;
- inspect the state of all OwlCam user services;
- see Pi uptime, available memory, disk space, load, and active Wi-Fi;
- read the latest 100 journal lines from one allowlisted OwlCam service;
- verify Firebase redirect status, target, and response time.

Firebase Analytics is not configured, so the panel does not invent traffic
counts. The Firebase card reports operational redirect health. Actual visitor
metrics would require enabling Analytics and adding a server-side Google
Analytics Data API credential; no Google credential belongs in browser code.

## Configure login

Credentials are configured on the Pi, never in this repository or in browser
storage:

```bash
ssh shawn@100.123.8.55
owlcam-configure-admin
```

The script asks for a username and a password of at least 16 characters. It
stores only an scrypt hash in `~/.config/owlcam/admin.env`, mode `600`, then
restarts the admin service. Restarting signs out all existing sessions.

The login uses:

- a server-side, eight-hour session;
- a `Secure`, `HttpOnly`, `SameSite=Strict` cookie;
- a session-bound CSRF token for stream changes and logout;
- a ten-attempt, fifteen-minute login limit;
- exact same-origin checks for browser writes.

No password or session token is stored in JavaScript-accessible browser
storage.

## Control boundary

`owlcam-admin` is a separate loopback-only service on `127.0.0.1:8766`.
Tailscale maps `/admin` to it while the static site remains isolated and
read-only.

The API does not accept shell commands, unit names, file paths, or remote URLs.
It maps fixed request values to fixed `systemctl --user` and `journalctl --user`
argument arrays. Logs are restricted to five known units and capped at 200
lines server-side.

Only the stream can be stopped from the panel. Stopping the site, admin service,
or Tailscale ingress would destroy the control surface during the request and
could strand the camera. Use SSH for those maintenance operations.

## API contract

All responses are JSON with `Cache-Control: no-store`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/api/session` | Check the current session |
| `POST` | `/admin/api/session` | Sign in |
| `DELETE` | `/admin/api/session` | Sign out |
| `GET` | `/admin/api/status` | Service and Pi health |
| `POST` | `/admin/api/stream` | Start or stop the stream |
| `GET` | `/admin/api/logs?service=stream&lines=100` | Bounded service journal |
| `GET` | `/admin/api/firebase` | Firebase redirect health |

## Recovery

If the panel says the admin service is unavailable:

```bash
ssh shawn@100.123.8.55
systemctl --user status owlcam-admin
journalctl --user -u owlcam-admin -n 100 --no-pager
curl -sS http://127.0.0.1:8766/api/session
```

An unconfigured service remains up but rejects login with HTTP 503. Run
`owlcam-configure-admin` to create the private credential file.
