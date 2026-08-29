from pathlib import Path

from app import (
    DEFAULT_STREAM_URL,
    MOMENTS,
    render_about_page,
    render_moments_page,
    render_page,
)
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
    assert ">Live<" not in html
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
    assert "aquaticmanagementgroup.com" not in html
    assert "AMG executive team" not in html
    assert "Share the OwlCam moments" in html
    assert ">Live<" not in html
    assert "Braxton" not in html
    assert "Greg Blum" not in html
    assert "Mackenzie" not in html
    assert 'href="/"' in html


def test_moments_page_has_placeholder_media_stories_and_sorting():
    html = render_moments_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>Owl Moments — Carver OwlCam</title>" in html
    assert len(MOMENTS) == 5
    assert sum(item["type"] == "photo" for item in MOMENTS) == 4
    assert sum(item["type"] == "video" for item in MOMENTS) == 1
    assert html.count("NEST ARCHIVE") == 4
    assert html.count("PLACEHOLDER") >= 1
    assert html.count("AI-GENERATED STORY") == len(MOMENTS)
    assert 'data-sort-key="filename"' in html
    assert 'data-sort-key="timestamp"' in html
    assert 'data-sort-key="type"' in html
    assert 'data-sort-key="subject"' in html
    assert 'src="/assets/moments/nest-box-build.jpg"' in html
    assert 'src="/assets/moments/owlet-in-doorway.jpg"' in html
    assert 'src="/assets/moments/owlet-on-ledge.jpg"' in html
    assert 'src="/assets/moments/adult-barred-owl.jpg"' in html
    assert 'src="/assets/moments/mole-delivery.webm"' in html
    assert 'src="/assets/moments.js"' in html
    assert 'href="/moments"' in html
    assert "capture dates were not preserved" in html
    assert "Strix-varia" not in html


def test_build_writes_firebase_hosting_bundle(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assert (output / "index.html").is_file()
    assert (output / "about.html").is_file()
    assert (output / "moments.html").is_file()
    assert (output / "assets" / "styles.css").is_file()
    assert (output / "assets" / "player.js").is_file()
    assert (output / "assets" / "moments.js").is_file()
    assert (output / "assets" / "moments" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "mole-delivery.webm").is_file()
    assert not (output / "assets" / "moments" / "winter-watch.jpg").exists()
    index = (output / "index.html").read_text()
    about = (output / "about.html").read_text()
    moments = (output / "moments.html").read_text()
    assert "owlcam.tail31318f.ts.net" in index
    assert "Chris Carver" in about
    assert "Braxton" not in about
    assert "Owl Moments" in moments
