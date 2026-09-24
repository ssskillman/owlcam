#!/usr/bin/env python3
"""Serve the built site and proxy the Pi's HLS mounts under one origin.

Local preview only. Production serves both from the Pi itself
(pi/scripts/site_server.py); this exists so the same relative /owl URL works
on a laptop without shipping a dev-only override into the page.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HLS_PATHS = ("/owl/", "/owl2/")


class PreviewHandler(SimpleHTTPRequestHandler):
    hls_port = 8888
    diagnostics_port = 8765

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        if self.path.startswith(HLS_PATHS):
            self._proxy(self.hls_port)
            return
        if self.path == "/diagnostics" or self.path.startswith("/diagnostics/"):
            self._proxy(self.diagnostics_port)
            return
        super().do_GET()

    def _proxy(self, port: int) -> None:
        upstream = f"http://127.0.0.1:{port}{self.path}"
        try:
            with urllib.request.urlopen(upstream, timeout=10) as response:
                body = response.read()
                content_type = response.headers.get(
                    "Content-Type", "application/octet-stream"
                )
        except urllib.error.HTTPError as error:
            self.send_error(error.code, "upstream rejected the request")
            return
        except OSError:
            # The tunnel is down or the Pi is not publishing. 502 tells the
            # player this is a path problem, not a resting camera.
            self.send_error(502, "cannot reach the Pi stream through the tunnel")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    site = Path(sys.argv[1])
    port = int(sys.argv[2])
    hls_port = int(sys.argv[3])
    diagnostics_port = int(sys.argv[4])
    PreviewHandler.hls_port = hls_port
    PreviewHandler.diagnostics_port = diagnostics_port
    handler = partial(PreviewHandler, directory=str(site))
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    main()
