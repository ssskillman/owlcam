#!/usr/bin/env python3
"""Serves the OwlCam site from the Pi so the page and the video share one origin.

The page used to be hosted on Firebase while the video came from the Pi's
Tailscale name. On any device running Tailscale, MagicDNS resolves that name to
a private address, and a browser refuses to let a page on a public origin reach
a private address space:

    blocked by CORS policy: Permission was denied for this request to access
    the `local` address space

Both the video and the vitals died together, which looked exactly like a
sleeping camera. Serving the page from the same host as the stream removes the
cross-origin hop, so there is nothing left to block, allow, or explain.
"""

from __future__ import annotations

import os
import re
import sys
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import unquote, urlsplit

HOST = "127.0.0.1"
PORT = int(os.environ.get("OWLCAM_SITE_PORT", "8080"))
SITE_ROOT = Path(os.environ.get("OWLCAM_SITE_ROOT", "/home/shawn/owlcam/site"))
CHUNK_SIZE = 64 * 1024

# build.py emits code assets as name.<12 hex>.ext, so the URL changes whenever
# the bytes change and the response can be cached forever. Anything without a
# fingerprint has a stable URL and must not be.
FINGERPRINTED = re.compile(r"\.[0-9a-f]{12}\.[^.]+$")

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

# Firebase applied these as hosting headers. Serving the page ourselves means
# sending them ourselves, or the move to one origin quietly drops them.
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# mimetypes is incomplete on a minimal Debian image, and a webm served as
# application/octet-stream does not play.
EXTRA_CONTENT_TYPES = {
    ".webm": "video/webm",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
}


class UnsatisfiableRange(ValueError):
    """A Range header that parses cleanly but falls outside the file."""


def resolve_file(url_path: str, root: Path) -> Path | None:
    """Map a URL path to a file inside root, or None if missing or escaping."""

    relative = unquote(urlsplit(url_path).path).lstrip("/")
    root_resolved = root.resolve()
    # normpath collapses ../ before the join; the prefix check below is what
    # actually enforces the boundary, including through symlinks.
    candidate = (
        (root_resolved / os.path.normpath(relative)).resolve()
        if relative
        else root_resolved
    )
    if candidate != root_resolved and not candidate.is_relative_to(root_resolved):
        return None

    if candidate.is_dir():
        candidate = candidate / "index.html"
    elif not candidate.exists() and not candidate.suffix:
        # Firebase served /about from about.html via cleanUrls, and the nav
        # still links that way.
        candidate = candidate.with_suffix(".html")

    return candidate if candidate.is_file() else None


def content_type(path: Path) -> str:
    override = EXTRA_CONTENT_TYPES.get(path.suffix.lower())
    if override:
        return override
    guessed, _encoding = guess_type(path.name)
    return guessed or "application/octet-stream"


def cache_control(path: Path) -> str:
    if FINGERPRINTED.search(path.name):
        return "public, max-age=31536000, immutable"
    if path.suffix.lower() in (".html", ".json"):
        # A cached page hides a deploy until the TTL expires.
        return "no-cache"
    return "public, max-age=3600"


def parse_byte_range(header: str, size: int) -> tuple[int, int] | None:
    """Parse a single byte range into inclusive (start, end).

    Returns None when there is no usable range and the whole file should be
    sent. Safari will not play a video at all unless ranges are honoured, so
    this is required rather than an optimisation.
    """

    if not header or not header.startswith("bytes="):
        return None

    spec = header[len("bytes=") :].strip()
    if "," in spec or "-" not in spec:
        return None

    start_text, _, end_text = spec.partition("-")
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise UnsatisfiableRange("suffix range must be positive")
            return max(0, size - suffix_length), size - 1
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except UnsatisfiableRange:
        raise
    except ValueError:
        # An unparseable range is ignored, per RFC 9110.
        return None

    end = min(end, size - 1)
    if start > end or start >= size:
        raise UnsatisfiableRange("range falls outside the file")
    return start, end


class SiteHandler(BaseHTTPRequestHandler):
    server_version = "OwlCamSite"
    sys_version = ""
    # Keep-alive matters: one page pulls a stylesheet, two scripts, and a set
    # of images. Every response below therefore sends an exact Content-Length.
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._serve(include_body=True)

    def do_HEAD(self) -> None:
        self._serve(include_body=False)

    def _send_headers(self, target: Path | None) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        if target is not None:
            self.send_header("Cache-Control", cache_control(target))
            self.send_header(
                "Last-Modified",
                formatdate(target.stat().st_mtime, usegmt=True),
            )

    def _send_text(
        self,
        status: HTTPStatus,
        text: str,
        *,
        include_body: bool,
    ) -> None:
        body = text.encode()
        self.send_response(status)
        self._send_headers(None)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _serve(self, *, include_body: bool) -> None:
        target = resolve_file(self.path, SITE_ROOT)
        if target is None:
            self._send_text(
                HTTPStatus.NOT_FOUND,
                "Not found\n",
                include_body=include_body,
            )
            return

        try:
            size = target.stat().st_size
        except OSError:
            self._send_text(
                HTTPStatus.NOT_FOUND,
                "Not found\n",
                include_body=include_body,
            )
            return

        try:
            byte_range = parse_byte_range(self.headers.get("Range", ""), size)
        except UnsatisfiableRange:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self._send_headers(target)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        start, end = byte_range if byte_range else (0, size - 1)
        length = max(0, end - start + 1)

        self.send_response(
            HTTPStatus.PARTIAL_CONTENT if byte_range else HTTPStatus.OK
        )
        self._send_headers(target)
        self.send_header("Content-Type", content_type(target))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        if not include_body or not length:
            return

        with target.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, _format: str, *_args: object) -> None:
        # Every page view is several requests, and the journal lives on the SD
        # card. Tailscale already records who connected.
        return


def main() -> None:
    if not SITE_ROOT.is_dir():
        # Serve 404s rather than crash-looping, but do not let a missing deploy
        # look like a healthy service.
        print(f"warning: site root {SITE_ROOT} does not exist", file=sys.stderr)
    ThreadingHTTPServer((HOST, PORT), SiteHandler).serve_forever()


if __name__ == "__main__":
    main()
