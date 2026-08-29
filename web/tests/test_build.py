from pathlib import Path

from app import DEFAULT_STREAM_URL, render_page
from build import build_site


def test_page_uses_private_https_stream_and_accessible_player():
    html = render_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>Carver OwlCam — Live from the Nest</title>" in html
    assert DEFAULT_STREAM_URL.startswith("https://")
    assert DEFAULT_STREAM_URL in html
    assert 'integrity="sha384-' in html
    assert 'id="owlcam-player"' in html
    assert 'aria-label="Carver OwlCam livestream"' in html
    assert 'id="stream-status"' in html
    assert "Camera is resting" in html


def test_build_writes_firebase_hosting_bundle(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assert (output / "index.html").is_file()
    assert (output / "assets" / "styles.css").is_file()
    assert (output / "assets" / "player.js").is_file()
    assert "owlcam.tail31318f.ts.net" in (output / "index.html").read_text()
