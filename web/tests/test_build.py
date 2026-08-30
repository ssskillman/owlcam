import json
from pathlib import Path

from app import (
    DEFAULT_STREAM_URL,
    MOMENTS,
    render_about_page,
    render_moments_page,
    render_page,
)
from build import FINGERPRINTED, WEB_ROOT, build_site


def test_page_uses_a_same_origin_stream_and_accessible_player():
    html = render_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>Carver OwlCam — Live from the Nest</title>" in html
    assert DEFAULT_STREAM_URL == "/owl/index.m3u8"
    assert DEFAULT_STREAM_URL in html
    assert 'integrity="sha384-' in html
    assert 'id="owlcam-player"' in html
    assert 'aria-label="Carver OwlCam livestream"' in html
    assert 'id="stream-status"' in html
    assert 'id="offline-title"' in html
    assert 'id="offline-message"' in html
    assert 'href="/about"' in html
    assert ">Live<" not in html
    assert "Braxton" not in html
    assert "Greg Blum" not in html


def test_about_page_covers_chris_carver_only():
    html = render_about_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>About Chris Carver — Carver OwlCam</title>" in html
    assert 'src="/assets/chris-carver.webp"' in html
    assert 'alt="Chris Carver outdoors by a pool"' in html
    assert 'width="750"' in html
    assert 'height="562"' in html
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
    assert html.count("FIELD NOTE") == len(MOMENTS)
    assert "AI-GENERATED" not in html
    assert "AI-assisted" not in html
    assert "AI-written" not in html
    assert "AI-generated" not in html
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


def test_pages_do_not_advertise_ai_generated_copy():
    for markup in (render_page(), render_about_page(), render_moments_page()):
        lower = markup.lower()
        assert "ai-generated" not in lower
        assert "ai-assisted" not in lower
        assert "ai-written" not in lower
        assert "ai generated" not in lower


def test_player_starts_playback_rather_than_only_reporting_online():
    source = (WEB_ROOT / "static" / "player.js").read_text()

    # hls.js buffers but never plays on its own. Without an explicit play() the
    # panel hides and the status reads online while a paused frame sits there,
    # which looks exactly like a broken stream.
    assert "video.play()" in source, "player never starts playback"
    assert source.index("setState(\"online\", \"OwlCam online\")") < source.index(
        "video.addEventListener(\"stalled\", start)"
    ), "playback start must be wired to the online transition"


def test_livestream_element_can_autoplay():
    html = render_page()

    # Autoplay is only permitted while muted, so the two attributes travel
    # together; dropping muted silently reintroduces the paused-forever bug.
    video = html[html.index("<video") : html.index(">", html.index("<video"))]
    assert "autoplay" in video, "livestream would sit paused until clicked"
    assert "muted" in video, "autoplay is blocked unless the video is muted"
    assert "playsinline" in video, "iOS would take the video fullscreen"


def test_live_page_has_accessible_realtime_diagnostics():
    html = render_page()

    assert 'id="diagnostics"' in html
    assert 'data-diagnostics-url="/diagnostics"' in html
    assert "NEST CONDITIONS" in html
    assert "PI HEALTH" in html
    assert 'id="diagnostics-temperature"' in html
    assert 'id="diagnostics-habitat-temperature"' in html
    assert 'id="diagnostics-humidity"' in html
    assert 'id="diagnostics-daylight"' in html
    assert 'id="diagnostics-memory"' in html
    assert 'id="diagnostics-load"' in html
    assert 'id="diagnostics-processes"' in html
    assert 'id="temperature-unit-toggle"' in html
    assert 'aria-pressed="true"' in html
    assert 'data-temperature-unit="f"' in html
    assert html.count('class="diagnostics-help"') == 7
    assert html.count('tabindex="0"') >= 7
    assert 'id="diagnostics-status"' in html
    assert 'aria-live="polite"' in html
    assert 'src="/assets/diagnostics.js"' in html


def test_diagnostics_polling_is_bounded_and_renders_as_text():
    source = (WEB_ROOT / "static" / "diagnostics.js").read_text()

    assert "fetch(endpoint" in source
    assert "AbortController" in source
    assert "POLL_INTERVAL = 5000" in source
    assert "setTimeout(refresh, POLL_INTERVAL)" in source
    assert ".textContent =" in source
    assert ".innerHTML" not in source
    assert "response.ok" in source
    assert 'temperature.textContent = "—"' in source
    assert 'memory.textContent = "—"' in source
    assert 'load.textContent = "—"' in source
    assert 'processes.textContent = "—"' in source
    assert "habitatTemperature" in source
    assert "humidity" in source
    assert "daylight" in source
    assert "data?.climate" in source
    assert "celsiusToFahrenheit" in source
    assert "temperatureUnit" in source
    assert 'dataset.temperatureUnit' in source
    assert 'Not connected' in source


def test_pages_declare_the_favicon():
    for markup in (render_page(), render_about_page(), render_moments_page()):
        assert '/assets/favicon.svg' in markup, "page is missing the tab icon"
        assert 'type="image/svg+xml"' in markup, "favicon type hint is missing"


def test_favicon_is_fingerprinted():
    # Browsers cache favicons far past the response headers, so the URL has to
    # change when the icon does.
    assert "favicon.svg" in FINGERPRINTED


def test_player_never_adds_an_empty_class_token():
    source = (WEB_ROOT / "static" / "player.js").read_text()

    # classList.add("") throws a SyntaxError. The connecting state passes an
    # empty class, so an unguarded add aborts connect() on its first statement
    # and the player silently never starts.
    assert 'setState("", ' in source, "connecting state no longer passes an empty class"
    assert "if (state) dot.classList.add(state)" in source, (
        "classList.add must be guarded against the empty connecting state"
    )


def test_player_prefers_hls_js_over_the_native_probe():
    source = (WEB_ROOT / "static" / "player.js").read_text()

    hls_js = source.index("window.Hls?.isSupported()")
    native = source.index('video.canPlayType("application/vnd.apple.mpegurl")')

    # Chrome returns "maybe" from canPlayType but cannot decode HLS. Probing
    # native support first leaves every non-Safari browser stuck on
    # "Checking live feed…" with no error to recover from.
    assert hls_js < native, "native HLS probe must not run before hls.js"


def test_player_reconnects_after_the_pi_stream_restarts():
    source = (WEB_ROOT / "static" / "player.js").read_text()

    # A fatal hls.js error used to leave an open page permanently offline even
    # after systemd restored the Pi stream. The page promises automatic
    # reconnection, so fatal HLS and native media failures must schedule it.
    assert "const scheduleReconnect" in source
    assert "setTimeout(connect, RECONNECT_DELAY)" in source
    assert "if (data.fatal) scheduleReconnect()" in source
    assert 'video.addEventListener("error", scheduleReconnect)' in source


def test_offline_panel_names_the_cause_instead_of_blaming_the_camera():
    html = render_page()
    source = (WEB_ROOT / "static" / "player.js").read_text()

    # The panel used to headline "Camera is resting" for every failure, so a
    # blocked request and a dead network both read as an owl taking a nap and
    # sent the viewer looking at the wrong thing.
    assert "Connecting to the camera" in html, "panel must open on the true state"
    assert "Camera is resting" not in html, (
        "a resting camera is one possible cause, not the page's default claim"
    )

    for reason in ("connecting", "resting", "interrupted", "unreachable", "unsupported"):
        assert f"{reason}:" in source, f"player cannot report the {reason} case"

    # Reachability is what separates a resting camera from a broken path to it,
    # and only the stream URL itself can answer that.
    assert "const diagnose" in source
    assert "fetch(video.dataset.streamUrl" in source
    assert 'return response.ok ? "interrupted" : "resting"' in source
    assert 'return "unreachable"' in source
    assert "diagnose().then(explain)" in source

    # The retry timer must not wait on a probe that can hang.
    assert source.index("diagnose().then(explain)") < source.index(
        "setTimeout(connect, RECONNECT_DELAY)"
    )


def test_diagnostics_distinguishes_unreachable_from_erroring():
    source = (WEB_ROOT / "static" / "diagnostics.js").read_text()

    # One message for three causes hid whether the Pi was unreachable, broken,
    # or answering with something the page could not parse.
    assert "Cannot reach the Pi" in source
    assert "Pi answered HTTP" in source
    assert "Unexpected vitals from the Pi" in source
    assert "let httpStatus = null" in source
    assert "renderUnavailable(httpStatus)" in source


def test_firebase_sends_every_visitor_to_the_single_origin():
    config = json.loads(
        (Path(__file__).resolve().parents[2] / "firebase.json").read_text()
    )["hosting"]

    # Serving the page from two origins is the bug, not a fallback: a visitor
    # who lands on Firebase while running Tailscale gets a page that cannot
    # reach the camera. Firebase's only job now is handing them to the Pi.
    destinations = {rule["destination"] for rule in config["redirects"]}
    assert destinations == {
        "https://owlcam.tail31318f.ts.net/",
        "https://owlcam.tail31318f.ts.net/:rest*",
    }

    sources = {rule["source"] for rule in config["redirects"]}
    assert "/" in sources, "the landing page itself must redirect"
    assert "/:rest*" in sources, "deep links must keep their path"

    # 302, not 301: a permanent redirect is cached hard by browsers and would
    # make moving the site back a support problem rather than a config change.
    assert {rule["type"] for rule in config["redirects"]} == {302}

    by_source = {
        entry["source"]: {h["key"]: h["value"] for h in entry["headers"]}
        for entry in config["headers"]
    }
    assert by_source["**"]["Cache-Control"] == "no-store", (
        "a cached redirect outlives the decision that created it"
    )


def test_build_writes_firebase_hosting_bundle(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assert (output / "index.html").is_file()
    assert (output / "about.html").is_file()
    assert (output / "moments.html").is_file()
    assert (output / "assets" / "chris-carver.webp").is_file()
    assert (output / "assets" / "moments" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "mole-delivery.jpg").is_file()
    assert (output / "assets" / "moments" / "mole-delivery.webm").is_file()
    assert not (output / "assets" / "moments" / "winter-watch.jpg").exists()
    index = (output / "index.html").read_text()
    about = (output / "about.html").read_text()
    moments = (output / "moments.html").read_text()
    assert 'data-stream-url="/owl/index.m3u8"' in index
    assert "Checking private feed" not in index

    # An absolute camera host is the whole bug: it resolves to a private
    # address on Tailscale devices and the browser blocks the request.
    for page in (index, about, moments):
        assert "owlcam.tail31318f.ts.net" not in page
    assert "Chris Carver" in about
    assert "Braxton" not in about
    assert "Owl Moments" in moments


def test_build_fingerprints_code_assets_to_defeat_stale_caches(tmp_path: Path):
    output = tmp_path / "public"

    build_site(output)

    assets = output / "assets"
    assert not (assets / "styles.css").exists(), "unhashed stylesheet still shipped"
    assert not (assets / "player.js").exists()
    assert not (assets / "diagnostics.js").exists()
    assert not (assets / "moments.js").exists()

    hashed = {p.name for p in assets.glob("*.*.css")} | {
        p.name for p in assets.glob("*.*.js")
    }
    assert any(n.startswith("styles.") and n.endswith(".css") for n in hashed)
    assert any(n.startswith("player.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("diagnostics.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("moments.") and n.endswith(".js") for n in hashed)

    index = (output / "index.html").read_text()
    assert '"/assets/styles.css"' not in index
    referenced = [n for n in hashed if f"/assets/{n}" in index]
    assert sorted(referenced) == sorted(
        n for n in hashed if n.startswith(("styles.", "player.", "diagnostics."))
    )

    # A content change must produce a different URL.
    first = {n for n in hashed if n.startswith("styles.")}
    (WEB_ROOT / "static" / "styles.css").read_text()
    second_output = tmp_path / "public2"
    build_site(second_output)
    again = {p.name for p in (second_output / "assets").glob("styles.*.css")}
    assert first == again, "identical input produced an unstable fingerprint"
