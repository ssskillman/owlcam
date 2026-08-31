import importlib.util
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "site_server.py"
SPEC = importlib.util.spec_from_file_location("owlcam_site", MODULE_PATH)
site = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(site)


def build_site_root(directory: str) -> Path:
    root = Path(directory)
    (root / "index.html").write_text("<h1>live</h1>")
    (root / "about.html").write_text("<h1>about</h1>")
    assets = root / "assets"
    assets.mkdir()
    (assets / "styles.6b71a5b87cfb.css").write_text("body{}")
    (assets / "owl.webp").write_bytes(b"webp-bytes")
    (assets / "clip.webm").write_bytes(bytes(range(256)) * 4)
    (root / "secret.txt").write_text("not part of the site")
    return root


class PathResolutionTests(unittest.TestCase):
    def test_maps_urls_to_files_including_clean_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = build_site_root(directory)

            self.assertEqual(site.resolve_file("/", root).name, "index.html")
            self.assertEqual(site.resolve_file("", root).name, "index.html")
            # Firebase's cleanUrls served /about from about.html, and the site
            # nav still links that way.
            self.assertEqual(site.resolve_file("/about", root).name, "about.html")
            self.assertEqual(site.resolve_file("/about/", root).name, "about.html")
            self.assertEqual(
                site.resolve_file("/assets/owl.webp", root).name, "owl.webp"
            )
            # A query string is not part of the file path.
            self.assertEqual(
                site.resolve_file("/about?utm=1", root).name, "about.html"
            )
            self.assertIsNone(site.resolve_file("/nope", root))
            self.assertIsNone(site.resolve_file("/nope.html", root))

    def test_refuses_to_serve_anything_outside_the_site_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = build_site_root(directory) / "assets"

            # The site root is assets/, so its own parent is off limits even
            # though the files plainly exist.
            for attempt in (
                "/../secret.txt",
                "/../../etc/passwd",
                "/%2e%2e/secret.txt",
                "/assets/../../secret.txt",
                "/....//secret.txt",
            ):
                self.assertIsNone(
                    site.resolve_file(attempt, root),
                    f"{attempt} escaped the site root",
                )


class CachingAndTypeTests(unittest.TestCase):
    def test_only_fingerprinted_assets_are_cached_forever(self):
        # A fingerprinted URL changes when its bytes change, so it can be held
        # forever. A stable URL cannot, or a deploy stays invisible.
        immutable = site.cache_control(Path("styles.6b71a5b87cfb.css"))
        self.assertIn("immutable", immutable)
        self.assertIn("max-age=31536000", immutable)

        self.assertEqual(site.cache_control(Path("index.html")), "no-cache")
        self.assertEqual(
            site.cache_control(Path("owl.webp")), "public, max-age=3600"
        )
        self.assertNotIn(
            "immutable", site.cache_control(Path("assets/moments/owl.jpg"))
        )

    def test_media_types_debian_does_not_know_are_still_correct(self):
        # A webm served as application/octet-stream does not play.
        self.assertEqual(site.content_type(Path("clip.webm")), "video/webm")
        self.assertEqual(site.content_type(Path("owl.webp")), "image/webp")
        self.assertEqual(site.content_type(Path("index.html")), "text/html")


class ByteRangeTests(unittest.TestCase):
    def test_parses_the_range_forms_browsers_actually_send(self):
        self.assertEqual(site.parse_byte_range("bytes=0-99", 1000), (0, 99))
        self.assertEqual(site.parse_byte_range("bytes=100-", 1000), (100, 999))
        self.assertEqual(site.parse_byte_range("bytes=-100", 1000), (900, 999))
        # An end past the file is clamped rather than rejected.
        self.assertEqual(site.parse_byte_range("bytes=0-9999", 1000), (0, 999))

    def test_ignores_ranges_it_cannot_use_and_rejects_impossible_ones(self):
        for ignored in ("", "items=0-1", "bytes=abc-def", "bytes=0-1,5-6"):
            self.assertIsNone(site.parse_byte_range(ignored, 1000))

        for impossible in ("bytes=1000-", "bytes=2000-3000", "bytes=-0"):
            with self.assertRaises(site.UnsatisfiableRange):
                site.parse_byte_range(impossible, 1000)


class ServedResponseTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = build_site_root(self._directory.name)
        patcher = patch.object(site, "SITE_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), site.SiteHandler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_serves_the_page_with_the_headers_firebase_used_to_add(self):
        with urlopen(f"{self.base}/", timeout=5) as response:
            body = response.read().decode()
            headers = response.headers

        self.assertEqual(body, "<h1>live</h1>")
        # Hosting the page ourselves means these are ours to send now.
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("camera=()", headers["Permissions-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-cache")

        # Same origin as the stream is the entire point, so the policy no
        # longer needs to name a separate media host.
        self.assertIn("media-src 'self' blob:", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn(
            "https://www.gstatic.com",
            headers["Content-Security-Policy"],
        )
        self.assertIn(
            "https://www.googletagmanager.com",
            headers["Content-Security-Policy"],
        )
        self.assertIn(
            "https://www.google-analytics.com",
            headers["Content-Security-Policy"],
        )
        self.assertIn(
            "https://firebaseinstallations.googleapis.com",
            headers["Content-Security-Policy"],
        )

    def test_advertises_and_honours_byte_ranges_so_safari_plays_video(self):
        expected = (self.root / "assets" / "clip.webm").read_bytes()

        with urlopen(f"{self.base}/assets/clip.webm", timeout=5) as response:
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")
            self.assertEqual(response.read(), expected)

        request = Request(
            f"{self.base}/assets/clip.webm", headers={"Range": "bytes=10-19"}
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(
                response.headers["Content-Range"], f"bytes 10-19/{len(expected)}"
            )
            self.assertEqual(response.headers["Content-Length"], "10")
            self.assertEqual(response.read(), expected[10:20])

    def test_reports_an_impossible_range_instead_of_sending_the_whole_file(self):
        request = Request(
            f"{self.base}/assets/clip.webm",
            headers={"Range": f"bytes={10**6}-"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)

        self.assertEqual(caught.exception.code, 416)
        caught.exception.close()

    def test_head_returns_the_length_without_the_body(self):
        request = Request(f"{self.base}/assets/owl.webp", method="HEAD")
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Length"], "10")
            self.assertEqual(response.headers["Content-Type"], "image/webp")
            self.assertEqual(response.read(), b"")

    def test_fingerprinted_assets_are_cacheable_and_pages_are_not(self):
        with urlopen(f"{self.base}/assets/styles.6b71a5b87cfb.css", timeout=5) as r:
            self.assertIn("immutable", r.headers["Cache-Control"])
        with urlopen(f"{self.base}/about", timeout=5) as r:
            self.assertEqual(r.headers["Cache-Control"], "no-cache")
            self.assertEqual(r.read().decode(), "<h1>about</h1>")

    def test_missing_paths_and_escape_attempts_both_return_404(self):
        for path in ("/missing", "/../secret.txt", "/assets/"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(f"{self.base}{path}", timeout=5)
            self.assertEqual(caught.exception.code, 404, path)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()
