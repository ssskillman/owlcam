import json
from pathlib import Path

from app import (
    DEFAULT_STREAM_URL,
    MOMENTS,
    render_about_page,
    render_moments_page,
    render_page,
)
from build import WEB_ROOT, build_site


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
    assert 'src="/assets/moments/mole-delivery.webm"' in html
    assert 'poster="/assets/moments/thumbs/mole-delivery.jpg"' in html
    assert 'src="/assets/moments.js"' in html
    assert 'href="/moments"' in html
    assert "capture dates were not preserved" in html
    assert "Strix-varia" not in html


def test_photo_moments_load_thumbnails_that_open_full_size():
    html = render_moments_page()

    for item in MOMENTS:
        if item["type"] != "photo":
            continue
        stem = item["filename"].rsplit(".", 1)[0]
        thumb = f'src="/assets/moments/thumbs/{stem}.jpg"'
        full = f'href="/assets/moments/{item["filename"]}"'
        assert thumb in html, f"{item['filename']} does not use a thumbnail"
        assert full in html, f"{item['filename']} thumbnail does not open full size"

    # The heavy originals must not be what the grid loads.
    assert 'src="/assets/moments/nest-box-build.jpg"' not in html
    assert 'src="/assets/moments/adult-barred-owl.jpg"' not in html
    assert html.count("View full size") == 4


def test_hosting_config_revalidates_code_and_allows_the_stream_host():
    config = json.loads(
        (Path(__file__).resolve().parents[2] / "firebase.json").read_text()
    )
    headers = config["hosting"]["headers"]
    by_source = {
        entry["source"]: {h["key"]: h["value"] for h in entry["headers"]}
        for entry in headers
    }

    stream_host = DEFAULT_STREAM_URL.split("/owl/")[0]
    csp = by_source["**"]["Content-Security-Policy"]
    assert f"media-src 'self' {stream_host}" in csp
    assert f"connect-src 'self' {stream_host}" in csp

    # Pages must revalidate, or a deploy stays invisible behind a stale cache.
    assert "no-cache" in by_source["**"]["Cache-Control"]

    # Fingerprinted code can be cached hard, because a change means a new URL.
    code = by_source["/assets/**/*.@(css|js)"]["Cache-Control"]
    assert "immutable" in code
    assert "max-age=31536000" in code

    images = by_source["/assets/**/*.@(jpg|jpeg|png|webp|webm|svg|ico|woff2)"]
    assert "max-age=3600" in images["Cache-Control"]


def test_build_writes_firebase_hosting_bundle(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assert (output / "index.html").is_file()
    assert (output / "about.html").is_file()
    assert (output / "moments.html").is_file()
    assert (output / "assets" / "moments" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "mole-delivery.jpg").is_file()
    assert (output / "assets" / "moments" / "mole-delivery.webm").is_file()
    assert not (output / "assets" / "moments" / "winter-watch.jpg").exists()
    index = (output / "index.html").read_text()
    about = (output / "about.html").read_text()
    moments = (output / "moments.html").read_text()
    assert "owlcam.tail31318f.ts.net" in index
    assert "Chris Carver" in about
    assert "Braxton" not in about
    assert "Owl Moments" in moments


def test_build_fingerprints_code_assets_to_defeat_stale_caches(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assets = output / "assets"
    assert not (assets / "styles.css").exists(), "unhashed stylesheet still shipped"
    assert not (assets / "player.js").exists()
    assert not (assets / "moments.js").exists()

    hashed = {p.name for p in assets.glob("*.*.css")} | {
        p.name for p in assets.glob("*.*.js")
    }
    assert any(n.startswith("styles.") and n.endswith(".css") for n in hashed)
    assert any(n.startswith("player.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("moments.") and n.endswith(".js") for n in hashed)

    index = (output / "index.html").read_text()
    assert '"/assets/styles.css"' not in index
    referenced = [n for n in hashed if f"/assets/{n}" in index]
    assert sorted(referenced) == sorted(
        n for n in hashed if n.startswith(("styles.", "player."))
    )

    # A content change must produce a different URL.
    first = {n for n in hashed if n.startswith("styles.")}
    (WEB_ROOT / "static" / "styles.css").read_text()
    second_output = tmp_path / "public2"
    build_site(second_output)
    again = {p.name for p in (second_output / "assets").glob("styles.*.css")}
    assert first == again, "identical input produced an unstable fingerprint"
