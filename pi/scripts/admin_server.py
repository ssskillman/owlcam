#!/usr/bin/env python3
"""Authenticated, allowlisted administration API for OwlCam.

This service deliberately does not accept commands, unit names, file paths, or
URLs from the browser. It exposes a small fixed contract: inspect health, read
bounded logs from known OwlCam units, and start or stop the camera stream.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


HOST = "127.0.0.1"
PORT = int(os.environ.get("OWLCAM_ADMIN_PORT", "8766"))
SESSION_COOKIE = "__Host-owlcam_admin"
SESSION_TTL_SECONDS = 8 * 60 * 60
MAX_BODY_BYTES = 4096
FIREBASE_URL = "https://carver-owlcam-72343.web.app/"
SERVICE_UNITS = {
    "media": "owlcam-mediamtx.service",
    "stream": "owlcam-stream.service",
    "site": "owlcam-site.service",
    "diagnostics": "owlcam-diagnostics.service",
    "admin": "owlcam-admin.service",
}


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a portable scrypt password record; never persist plaintext."""

    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=actual_salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt:16384:8:1:{_b64encode(actual_salt)}:{_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split(":")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64decode(expected)),
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


class SessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._sessions: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def create(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        with self._lock:
            self._prune()
            self._sessions[token] = (csrf, self.clock() + self.ttl_seconds)
        return token, csrf

    def authenticate(self, token: str | None) -> str | None:
        if not token:
            return None
        with self._lock:
            self._prune()
            record = self._sessions.get(token)
            return record[0] if record else None

    def delete(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def _prune(self) -> None:
        now = self.clock()
        expired = [
            token for token, (_csrf, expiry) in self._sessions.items() if expiry <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)


class LoginRateLimiter:
    def __init__(
        self,
        *,
        limit: int = 10,
        window_seconds: int = 15 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = self.clock()
        with self._lock:
            attempts = self._attempts[client]
            while attempts and attempts[0] <= now - self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.limit:
                return False
            attempts.append(now)
            return True

    def clear(self, client: str) -> None:
        with self._lock:
            self._attempts.pop(client, None)


def _run(command: list[str], *, timeout: float = 4) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def service_state(unit: str) -> str:
    result = _run(["systemctl", "--user", "is-active", unit])
    state = result.stdout.strip()
    return state if state else "unknown"


def stream_state() -> dict[str, Any]:
    state = service_state(SERVICE_UNITS["stream"])
    return {"state": state, "isEnabled": state in ("active", "activating")}


def set_stream_enabled(enabled: bool) -> dict[str, Any]:
    verb = "start" if enabled else "stop"
    result = _run(
        ["systemctl", "--user", verb, SERVICE_UNITS["stream"]],
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError("stream control failed")
    print(
        f"{datetime.now(UTC).isoformat(timespec='seconds')} "
        f"admin stream_{'started' if enabled else 'stopped'}",
        flush=True,
    )
    return stream_state()


def read_service_logs(service: str, lines: int) -> list[str]:
    unit = SERVICE_UNITS[service]
    result = _run(
        [
            "journalctl",
            "--user-unit",
            unit,
            "--lines",
            str(lines),
            "--no-pager",
            "--output",
            "short-iso",
        ],
        timeout=5,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("logs unavailable")
    return result.stdout.splitlines()


def _read_mem_available_gib() -> float | None:
    try:
        for line in open("/proc/meminfo", encoding="utf-8"):
            if line.startswith("MemAvailable:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except (OSError, ValueError):
        return None
    return None


def _wifi_connection() -> str | None:
    try:
        result = _run(
            ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "wlan0"],
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value and value != "--" else None


def collect_status() -> dict[str, Any]:
    services = {name: service_state(unit) for name, unit in SERVICE_UNITS.items()}
    try:
        uptime_seconds = int(float(open("/proc/uptime", encoding="utf-8").read().split()[0]))
    except (OSError, ValueError, IndexError):
        uptime_seconds = None
    try:
        disk = shutil.disk_usage("/")
        disk_free_gib = round(disk.free / 1024**3, 1)
    except OSError:
        disk_free_gib = None
    return {
        "stream": {
            "state": services["stream"],
            "isEnabled": services["stream"] in ("active", "activating"),
        },
        "services": services,
        "host": {
            "uptimeSeconds": uptime_seconds,
            "memoryAvailableGiB": _read_mem_available_gib(),
            "diskFreeGiB": disk_free_gib,
            "load1": round(os.getloadavg()[0], 2),
            "wifiConnection": _wifi_connection(),
        },
        "sampledAt": datetime.now(UTC).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def firebase_edge_status() -> dict[str, Any]:
    started = time.monotonic()
    request = Request(FIREBASE_URL, method="HEAD")
    try:
        with build_opener(_NoRedirect).open(request, timeout=5) as response:
            status = response.status
            location = response.headers.get("Location")
    except HTTPError as error:
        status = error.code
        location = error.headers.get("Location")
        error.close()
    except (URLError, TimeoutError, OSError):
        return {
            "reachable": False,
            "status": None,
            "redirectTarget": None,
            "latencyMs": round((time.monotonic() - started) * 1000),
            "note": "Firebase Analytics is not configured; this checks redirect health.",
        }
    return {
        "reachable": True,
        "status": status,
        "redirectTarget": location,
        "latencyMs": round((time.monotonic() - started) * 1000),
        "note": "Firebase Analytics is not configured; this checks redirect health.",
    }


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "OwlCamAdmin"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def sessions(self) -> SessionStore:
        return self.server.sessions

    def _path(self) -> str:
        path = urlsplit(self.path).path
        return path[len("/admin") :] if path == "/admin" or path.startswith("/admin/") else path

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        cookie: str | None = None,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.send_header("Connection", "close")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _error(self, status: int, code: str, message: str) -> None:
        self._send_json(status, {"error": {"code": code, "message": message}})

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "").split(":", 1)[0]
        return origin == f"https://{host}"

    def _read_json(self) -> dict[str, Any] | None:
        if self.headers.get_content_type() != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "CONTENT_TYPE", "JSON required")
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "BODY_SIZE", "Invalid body")
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._error(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "Invalid JSON")
            return None
        if not isinstance(payload, dict):
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_INPUT", "Object required")
            return None
        return payload

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except ValueError:
            return None
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _require_auth(self, *, csrf: bool = False) -> tuple[str, str] | None:
        token = self._session_token()
        expected_csrf = self.sessions.authenticate(token)
        if not expected_csrf:
            self._error(HTTPStatus.UNAUTHORIZED, "UNAUTHENTICATED", "Sign in required")
            return None
        if csrf and not hmac.compare_digest(
            self.headers.get("X-Owlcam-Csrf", ""),
            expected_csrf,
        ):
            self._error(HTTPStatus.FORBIDDEN, "CSRF", "Request verification failed")
            return None
        return token or "", expected_csrf

    def do_GET(self) -> None:
        path = self._path()
        if path == "/api/session":
            token = self._session_token()
            csrf = self.sessions.authenticate(token)
            self._send_json(
                HTTPStatus.OK,
                {"authenticated": bool(csrf), "csrfToken": csrf},
            )
            return
        auth = self._require_auth()
        if not auth:
            return
        _token, csrf = auth
        if path == "/api/status":
            try:
                payload = collect_status()
            except (OSError, subprocess.SubprocessError):
                self._error(HTTPStatus.SERVICE_UNAVAILABLE, "STATUS_UNAVAILABLE", "Status unavailable")
                return
            payload["csrfToken"] = csrf
            self._send_json(HTTPStatus.OK, payload)
            return
        if path == "/api/firebase":
            self._send_json(HTTPStatus.OK, firebase_edge_status())
            return
        if path == "/api/logs":
            query = parse_qs(urlsplit(self.path).query)
            service = query.get("service", [""])[0]
            if service not in SERVICE_UNITS:
                self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_SERVICE", "Unknown service")
                return
            try:
                lines = min(200, max(1, int(query.get("lines", ["100"])[0])))
                payload = read_service_logs(service, lines)
            except ValueError:
                self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_LINES", "Invalid line count")
                return
            except (OSError, RuntimeError, subprocess.SubprocessError):
                self._error(HTTPStatus.SERVICE_UNAVAILABLE, "LOGS_UNAVAILABLE", "Logs unavailable")
                return
            self._send_json(HTTPStatus.OK, {"service": service, "lines": payload})
            return
        self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Not found")

    def do_POST(self) -> None:
        path = self._path()
        if not self._origin_allowed():
            self._error(HTTPStatus.FORBIDDEN, "ORIGIN", "Origin not allowed")
            return
        if path == "/api/session":
            self._login()
            return
        auth = self._require_auth(csrf=True)
        if not auth:
            return
        if path != "/api/stream":
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Not found")
            return
        payload = self._read_json()
        if payload is None:
            return
        enabled = payload.get("enabled")
        if type(enabled) is not bool or set(payload) != {"enabled"}:
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_INPUT", "enabled must be boolean")
            return
        token, _csrf = auth
        if not self.server.action_limiter.allow(token):
            self._error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "RATE_LIMITED",
                "Wait before changing the stream again",
            )
            return
        try:
            stream = set_stream_enabled(enabled)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "CONTROL_FAILED", "Stream control failed")
            return
        self._send_json(HTTPStatus.OK, {"stream": stream})

    def _login(self) -> None:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",")[-1].strip()
        try:
            client = str(ipaddress.ip_address(forwarded))
        except ValueError:
            client = self.client_address[0]
        if not self.server.login_limiter.allow(client):
            self._error(HTTPStatus.TOO_MANY_REQUESTS, "RATE_LIMITED", "Try again later")
            return
        payload = self._read_json()
        if payload is None:
            return
        username = payload.get("username")
        password = payload.get("password")
        configured_hash = self.server.password_hash
        if not configured_hash:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "NOT_CONFIGURED", "Admin login is not configured")
            return
        valid = (
            isinstance(username, str)
            and isinstance(password, str)
            and len(username) <= 64
            and len(password) <= 1024
            and hmac.compare_digest(username, self.server.admin_username)
            and verify_password(password, configured_hash)
        )
        if not valid:
            self._error(HTTPStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "Invalid credentials")
            return
        self.server.login_limiter.clear(client)
        token, csrf = self.sessions.create()
        cookie = (
            f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
            "Secure; HttpOnly; SameSite=Strict"
        )
        self._send_json(
            HTTPStatus.OK,
            {"authenticated": True, "csrfToken": csrf},
            cookie=cookie,
        )

    def do_DELETE(self) -> None:
        if not self._origin_allowed():
            self._error(HTTPStatus.FORBIDDEN, "ORIGIN", "Origin not allowed")
            return
        if self._path() != "/api/session":
            self._error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Not found")
            return
        auth = self._require_auth(csrf=True)
        if not auth:
            return
        token, _csrf = auth
        self.sessions.delete(token)
        cookie = (
            f"{SESSION_COOKIE}=; Path=/; Max-Age=0; "
            "Secure; HttpOnly; SameSite=Strict"
        )
        self._send_json(HTTPStatus.OK, {"authenticated": False}, cookie=cookie)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AdminHandler)
    server.sessions = SessionStore()
    server.password_hash = os.environ.get("OWLCAM_ADMIN_PASSWORD_HASH", "")
    server.admin_username = os.environ.get("OWLCAM_ADMIN_USERNAME", "admin")
    server.login_limiter = LoginRateLimiter()
    server.action_limiter = LoginRateLimiter(limit=1, window_seconds=15)
    if not server.password_hash:
        print(
            "warning: OWLCAM_ADMIN_PASSWORD_HASH is unset; login is disabled",
            flush=True,
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
