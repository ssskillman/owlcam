from pathlib import Path

from app import DEFAULT_STREAM_URL, render_about_page, render_page
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
    assert 'href="/about"' in html
    assert "Braxton" not in html
    assert "Greg Blum" not in html


def test_about_page_covers_chris_carver_only():
    html = render_about_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>About Chris Carver — Carver OwlCam</title>" in html
    assert "Chris Carver" in html
    assert "Chief Service Officer" in html
    assert "Eagle Scout" in html
    assert "Camp Raven Knob" in html
    assert "Seven Oaks Swim Club" in html
    assert "NC State University" in html
    assert 'href="https://www.aquaticmanagementgroup.com/the-executive-team"' in html
    assert "Share the OwlCam moments" in html
    assert "Braxton" not in html
    assert "Greg Blum" not in html
    assert "Mackenzie" not in html
    assert 'href="/"' in html


def test_build_writes_firebase_hosting_bundle(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assert (output / "index.html").is_file()
    assert (output / "about.html").is_file()
    assert (output / "assets" / "styles.css").is_file()
    assert (output / "assets" / "player.js").is_file()
    index = (output / "index.html").read_text()
    about = (output / "about.html").read_text()
    assert "owlcam.tail31318f.ts.net" in index
    assert "Chris Carver" in about
    assert "Braxton" not in about
