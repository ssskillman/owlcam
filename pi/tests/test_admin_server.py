import importlib.util
import json
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "admin_server.py"
SPEC = importlib.util.spec_from_file_location("owlcam_admin", MODULE_PATH)
admin = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(admin)


def request_json(url, *, method="GET", payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    request_headers = dict(headers or {})
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=request_headers)
    with urlopen(request, timeout=5) as response:
        return response.status, response.headers, json.load(response)


class PasswordTests(unittest.TestCase):
    def test_hashes_passwords_with_scrypt_and_verifies_without_plaintext(self):
        encoded = admin.hash_password("correct horse battery staple")

        self.assertTrue(encoded.startswith("scrypt:"))
        self.assertNotIn("correct", encoded)
        self.assertTrue(admin.verify_password("correct horse battery staple", encoded))
        self.assertFalse(admin.verify_password("wrong", encoded))
        self.assertFalse(admin.verify_password("anything", "invalid"))


class SessionStoreTests(unittest.TestCase):
    def test_sessions_expire_and_csrf_is_bound_to_the_session(self):
        now = [100.0]
        store = admin.SessionStore(ttl_seconds=60, clock=lambda: now[0])
        token, csrf = store.create()

        self.assertEqual(store.authenticate(token), csrf)
        now[0] = 161.0
        self.assertIsNone(store.authenticate(token))


class RateLimiterTests(unittest.TestCase):
    def test_limits_each_source_independently_and_recovers_after_window(self):
        now = [100.0]
        limiter = admin.LoginRateLimiter(
            limit=2,
            window_seconds=60,
            clock=lambda: now[0],
        )

        self.assertTrue(limiter.allow("203.0.113.1"))
        self.assertTrue(limiter.allow("203.0.113.1"))
        self.assertFalse(limiter.allow("203.0.113.1"))
        self.assertTrue(limiter.allow("203.0.113.2"))
        now[0] = 161.0
        self.assertTrue(limiter.allow("203.0.113.1"))


class ServiceCommandTests(unittest.TestCase):
    @patch.object(admin, "_run")
    def test_log_reader_uses_user_unit_selector_and_fixed_allowlist(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "one\ntwo\n"

        self.assertEqual(admin.read_service_logs("stream", 20), ["one", "two"])
        command = run.call_args.args[0]
        self.assertEqual(
            command[:3],
            ["journalctl", "--user-unit", "owlcam-stream.service"],
        )
        self.assertNotIn("--user", command)

        with self.assertRaises(KeyError):
            admin.read_service_logs("../../etc/passwd", 20)


class AdminHTTPTests(unittest.TestCase):
    def setUp(self):
        self.sessions = admin.SessionStore(ttl_seconds=3600)
        self.server = admin.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            admin.AdminHandler,
        )
        self.server.sessions = self.sessions
        self.server.password_hash = admin.hash_password("nest-secret")
        self.server.admin_username = "admin"
        self.server.login_limiter = admin.LoginRateLimiter(limit=10, window_seconds=60)
        self.server.action_limiter = admin.LoginRateLimiter(limit=1, window_seconds=15)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.origin = "https://owlcam.tail31318f.ts.net"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def login(self):
        status, headers, payload = request_json(
            f"{self.base}/api/session",
            method="POST",
            payload={"username": "admin", "password": "nest-secret"},
            headers={"Origin": self.origin, "Host": "owlcam.tail31318f.ts.net"},
        )
        cookie = SimpleCookie()
        cookie.load(headers["Set-Cookie"])
        return status, headers, payload, cookie[admin.SESSION_COOKIE].value

    def test_login_sets_a_secure_server_side_cookie(self):
        status, headers, payload, _token = self.login()

        self.assertEqual(status, 200)
        self.assertTrue(payload["authenticated"])
        self.assertTrue(payload["csrfToken"])
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("nest-secret", cookie)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_login_rejects_bad_credentials_and_cross_origin_requests(self):
        for payload, origin, expected in (
            ({"username": "admin", "password": "wrong"}, self.origin, 401),
            (
                {"username": "admin", "password": "nest-secret"},
                "https://attacker.example",
                403,
            ),
        ):
            request = Request(
                f"{self.base}/api/session",
                data=json.dumps(payload).encode(),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Origin": origin,
                    "Host": "owlcam.tail31318f.ts.net",
                },
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, expected)
            error = json.load(caught.exception)
            self.assertIn("error", error)
            caught.exception.close()

    @patch.object(admin, "collect_status")
    def test_status_requires_authentication(self, collect_status):
        collect_status.return_value = {"stream": {"state": "active"}}
        unauthenticated = Request(f"{self.base}/api/status")
        with self.assertRaises(HTTPError) as caught:
            urlopen(unauthenticated, timeout=5)
        self.assertEqual(caught.exception.code, 401)
        caught.exception.close()

        _status, _headers, login, token = self.login()
        status, _headers, payload = request_json(
            f"{self.base}/api/status",
            headers={"Cookie": f"{admin.SESSION_COOKIE}={token}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["stream"]["state"], "active")
        self.assertEqual(payload["csrfToken"], login["csrfToken"])

    @patch.object(admin, "set_stream_enabled")
    def test_stream_control_requires_csrf_and_accepts_only_a_boolean(self, control):
        control.return_value = {"state": "inactive", "isEnabled": False}
        _status, _headers, login, token = self.login()
        cookie = {"Cookie": f"{admin.SESSION_COOKIE}={token}"}

        for payload, csrf, expected in (
            ({"enabled": False}, None, 403),
            ({"enabled": "false"}, login["csrfToken"], 422),
        ):
            headers = dict(cookie)
            if csrf:
                headers["X-Owlcam-Csrf"] = csrf
            request = Request(
                f"{self.base}/api/stream",
                data=json.dumps(payload).encode(),
                method="POST",
                headers={**headers, "Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, expected)
            caught.exception.close()

        status, _headers, payload = request_json(
            f"{self.base}/api/stream",
            method="POST",
            payload={"enabled": False},
            headers={**cookie, "X-Owlcam-Csrf": login["csrfToken"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["stream"]["state"], "inactive")
        control.assert_called_once_with(False)

        repeated = Request(
            f"{self.base}/api/stream",
            data=json.dumps({"enabled": True}).encode(),
            method="POST",
            headers={
                **cookie,
                "Content-Type": "application/json",
                "X-Owlcam-Csrf": login["csrfToken"],
            },
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(repeated, timeout=5)
        self.assertEqual(caught.exception.code, 429)
        caught.exception.close()

    @patch.object(admin, "read_service_logs")
    def test_logs_are_allowlisted_and_bounded(self, read_logs):
        read_logs.return_value = ["line one", "line two"]
        _status, _headers, _login, token = self.login()
        headers = {"Cookie": f"{admin.SESSION_COOKIE}={token}"}

        status, _headers, payload = request_json(
            f"{self.base}/api/logs?service=stream&lines=9999",
            headers=headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["lines"], ["line one", "line two"])
        read_logs.assert_called_once_with("stream", 200)

        request = Request(f"{self.base}/api/logs?service=../../etc/passwd")
        request.add_header("Cookie", f"{admin.SESSION_COOKIE}={token}")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 422)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
