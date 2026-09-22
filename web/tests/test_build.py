import json
import re
from pathlib import Path

from app import (
    DEFAULT_STREAM_URL,
    DEFAULT_USB_STREAM_URL,
    MOMENTS,
    render_about_page,
    render_identify_page,
    render_moments_page,
    render_page,
)
from build import FINGERPRINTED, WEB_ROOT, build_site


def test_page_uses_a_same_origin_stream_and_accessible_player():
    html = render_page()

    assert html.count("<!doctype html>") == 1
    assert "<title>Carver OwlCam — Live from the Nest</title>" in html
    assert DEFAULT_STREAM_URL == "/owl/index.m3u8"
    assert DEFAULT_USB_STREAM_URL == "/owl2/index.m3u8"
    assert DEFAULT_STREAM_URL in html
    assert DEFAULT_USB_STREAM_URL in html
    assert 'id="camera-source-toggle"' in html
    assert 'data-camera-source="nest"' in html
    assert 'data-camera-source="usb"' in html
    assert 'data-stream-url-usb="/owl2/index.m3u8"' in html
    assert 'integrity="sha384-' in html
    assert 'id="owlcam-player"' in html
    assert 'aria-label="Carver OwlCam livestream"' in html
    assert 'id="stream-status"' in html
    assert 'id="offline-title"' in html
    assert 'id="offline-message"' in html
    assert 'href="/about"' in html
    assert 'href="/identify"' in html
    assert "Upload &amp; Identify" in html
    assert ">Live<" not in html
    assert "Braxton" not in html
    assert "Greg Blum" not in html
    assert 'id="nav-signed-in"' in html
    assert 'id="capture-toast"' in html
    assert 'class="ledger-chip"' in html
    assert "saves / 24h" in html
    assert 'id="capture-toast-count"' in html
    assert 'src="/assets/home-status.js"' in html
    assert "data-api-origin=" in html


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
    assert 'src="/assets/moments-calendar.js"' in html
    assert 'src="/assets/moments-live.js"' in html
    assert 'id="moments-calendar-grid"' in html
    assert 'id="moments-day-table"' in html
    assert 'id="moments-calendar-offline"' in html
    assert "Activity calendar." in html
    assert 'id="moments-calendar-drawer"' in html
    assert "moments-calendar-drawer__summary" in html
    assert 'id="moments-calendar"' in html
    assert 'id="moments-live"' in html
    assert 'id="moments-archive"' in html
    assert 'class="moments-jump"' in html
    assert 'href="#moments-calendar"' in html
    assert html.index("Small moments.") < html.index("moments-calendar-drawer")
    assert "Open the calendar above to load nest activity." in html
    assert "What do V, E, and P mean?" in html
    assert 'src="/assets/theme.js"' in html
    assert 'id="nest-moments-grid"' in html
    assert 'id="nest-moments-status"' in html
    assert "From the nest." in html
    assert 'href="/moments"' in html
    assert "capture dates were not preserved" in html
    assert "Strix-varia" not in html


def test_moments_page_embeds_configured_api_origin(monkeypatch):
    import app as site_app

    monkeypatch.setattr(
        site_app, "ANIMAL_ID_API_ORIGIN", "https://id.example.ts.net:8443"
    )
    html = site_app.render_moments_page()
    assert 'data-api-origin="https://id.example.ts.net:8443"' in html


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


def test_identify_page_is_public_and_hides_model_controls():
    html = render_identify_page()

    assert "What animal" in html
    assert "did you spot?" in html
    assert "Identify animals" in html
    assert "Only JPG, PNG, and WebP image files are accepted." in html
    assert "yolov8" not in html.lower()
    assert "BioCLIP" not in html
    assert "candidate confidence" not in html
    assert 'id="identify-form"' in html
    assert "data-api-origin=" in html
    assert 'id="identify-drop"' in html
    assert 'src="/assets/identify.js"' in html
    assert "YOLO minimum" not in html
    source = (WEB_ROOT / "static" / "identify.js").read_text()
    assert "Analyzing photos…" in source
    assert "The photo-processing server is offline" in source
    assert "response.status < 500" in source
    assert "payload.detail" in source
    assert "YOLO crop" not in source
    assert "Crop of the largest animal" in source
    assert "owlcamTrack" in source
    assert ".innerHTML" not in source


def test_identify_page_has_a_hidden_flying_owl_progress_indicator():
    html = render_identify_page()

    # Decorative: the aria-live status paragraph is what announces progress.
    assert 'id="identify-loader"' in html
    assert 'aria-hidden="true"' in html
    assert "identify-owl" in html
    assert "<svg" in html

    css = (WEB_ROOT / "static" / "styles.css").read_text()
    assert "@keyframes owl-fly" in css
    assert "@keyframes owl-flap" in css
    assert ".identify-loader[hidden]" in css
    # Wings flapping forever is exactly what reduced-motion users opt out of.
    reduced = css.split("@media (prefers-reduced-motion: reduce)")[1]
    assert ".identify-owl" in reduced

    source = (WEB_ROOT / "static" / "identify.js").read_text()
    assert "identify-loader" in source
    assert "loader.hidden = false" in source
    assert "loader.hidden = true" in source


def test_identify_correction_form_stays_collapsed_until_asked_for():
    css = (WEB_ROOT / "static" / "styles.css").read_text()
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # The JS hides the block, but display on the class outranks the hidden
    # attribute's UA display:none, so every card rendered the correction
    # input, the note, the opt-in, and Send feedback all at once.
    assert "extra.hidden = true" in source
    assert ".identify-correction[hidden]" in css


def test_identify_verdict_buttons_carry_equal_weight():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # Styling one verdict as the primary action pushes people toward it, and
    # the answer is the data we are collecting.
    assert source.count('className = "identify-quiet"') >= 2
    assert "right.className = wrong.className" in source


def test_identify_cards_hide_rounding_noise_and_default_source():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # Cards listed alternatives that round to 0%, which is not a possibility.
    assert "ALTERNATIVE_FLOOR" in source
    # "The whole photo" is the default, so saying it on every card is noise.
    assert 'item.selected_source === "crop"' in source


def test_selected_photos_collapse_after_identification_starts():
    html = render_identify_page()
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    assert 'id="identify-selection"' in html
    assert 'id="identify-selection-summary"' in html
    assert html.index('id="identify-selection-summary"') < html.index(
        'id="identify-thumbs"'
    )
    assert "selection.open = false" in source
    assert "selected photo" in source


def test_identify_disclaimer_appears_once_above_all_result_cards():
    html = render_identify_page()
    source = (WEB_ROOT / "static" / "identify.js").read_text()
    disclaimer = (
        "Identification is generated by an AI wildlife model and may be incorrect."
    )

    assert html.count(disclaimer) == 1
    assert source.count(disclaimer) == 0
    assert html.index(disclaimer) < html.index('id="identify-results"')
    assert 'id="identify-results-disclaimer"' in html


def test_each_result_can_retry_only_its_original_photo():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    assert 'retry.textContent = "Retry identification"' in source
    assert "identifyFiles([originalFile])" in source
    assert "card.replaceWith(renderCard(" in source
    assert 'body.append("images", file, file.name)' in source
    assert "submittedFiles[index]" in source


def test_choose_photos_opens_the_picker_once_per_tap():
    html = render_identify_page()
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # The button sits inside the drop zone, so its click bubbles there too.
    # Two programmatic clicks in one gesture leave iOS Safari delivering a
    # change event with no files: no thumbnails, no message, nothing.
    drop = html.index('id="identify-drop"')
    zone = html[drop : html.index("</div>", drop)]
    assert 'id="identify-browse"' in zone, (
        "test assumes the button is nested inside the drop zone"
    )

    assert 'drop?.addEventListener("click", () => fileInput.click())' not in source
    # Both the tap path and the keyboard path bubble up from the button.
    assert source.count('closest("#identify-browse")') >= 2


def test_animals_identified_chart_loads_without_an_upload():
    source = (WEB_ROOT / "static" / "identify.js").read_text()
    css = (WEB_ROOT / "static" / "styles.css").read_text()

    # The chart is all-time history, so gating it behind an identification
    # hid it from everyone who came only to look.
    assert "loadSummary()" in source[source.rindex("if (!origin) {") :]
    # Desktop sits it beside the headline, in the gap the short headline left.
    assert "grid-row: 1" in css.split(".identify-summary {")[1].split("}")[0]


def test_feedback_does_not_promise_to_use_the_photo():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # Nothing in the repo retrains, and a feedback row carries no image bytes
    # and no job_id, so the photo could not be found again even if it were
    # kept. Asking permission to use it promised something impossible.
    assert "improve OwlCam" not in source
    assert "The photo is not kept." in source


def test_identify_checks_the_identifier_before_photos_are_picked():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # The inference host is a desktop that sleeps, so the page has to admit it
    # is unreachable up front instead of after an upload burns a minute.
    assert "/api/health" in source
    assert "checkHealth" in source
    # Picking photos must not re-enable a button the health check turned off.
    assert "|| offline" in source


def test_a_selection_that_yields_no_files_says_so():
    source = (WEB_ROOT / "static" / "identify.js").read_text()

    # Every reject path sets a status, but an empty list skipped the loop
    # entirely and failed silently, which is why the phone showed nothing.
    assert "No photos were added" in source


def test_identify_summary_is_above_results_and_hidden_until_loaded():
    html = render_identify_page()

    assert 'id="identify-summary"' in html
    assert 'id="identify-summary-total"' in html
    assert 'id="identify-chart"' in html
    assert html.index('id="identify-summary"') < html.index('id="identify-results"')
    summary_tag = html[html.index('id="identify-summary"') - 100 : html.index('id="identify-summary"')]
    assert "hidden" in summary_tag


def test_identify_summary_uses_native_drilldowns_and_semantic_bars():
    source = (WEB_ROOT / "static" / "identify.js").read_text()
    css = (WEB_ROOT / "static" / "styles.css").read_text()

    assert 'apiUrl("/api/animal-identification/summary")' in source
    assert 'document.createElement("details")' in source
    assert 'document.createElement("summary")' in source
    assert 'document.createElement("progress")' in source
    assert "loadSummary()" in source
    assert ".identify-chart progress" in css
    assert ".identify-species-counts" in css
    progress = _css_block(css, ".identify-chart progress {")
    assert "min-width: 0" in progress


def _css_block(css: str, header: str) -> str:
    """Body of one rule, brace-matched because keyframes nest their own."""
    start = css.index(header) + len(header)
    depth = 0
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[start : index + 1]
    raise AssertionError(f"unbalanced braces after {header}")


def test_flying_owl_crosses_the_loader_rather_than_the_viewport():
    css = (WEB_ROOT / "static" / "styles.css").read_text()
    fly = _css_block(css, "@keyframes owl-fly")

    # Travel was 105vw inside a container that main caps at 1440px, so on a
    # wide monitor the owl covered far more ground in the same time and spent
    # much of each lap off the right edge. Percentages of the loader do not
    # drift with the viewport.
    assert "vw" not in fly
    assert "100%" in fly


def test_flying_owl_glides_rather_than_darts():
    css = (WEB_ROOT / "static" / "styles.css").read_text()
    owl = _css_block(css, ".identify-owl {")
    wing = _css_block(css, ".identify-owl-wing {")

    lap = float(re.search(r"owl-fly (\d+(?:\.\d+)?)s", owl).group(1))
    flap = float(re.search(r"owl-flap (\d+(?:\.\d+)?)s", wing).group(1))
    # One lap in 3.2s read as darting. A wingbeat has to stay slow enough to
    # match the glide, or the owl looks like it is panicking.
    assert lap >= 6.0
    assert 0.4 <= flap <= 0.8


def test_identify_page_embeds_configured_api_origin(monkeypatch):
    import app as site_app

    monkeypatch.setattr(
        site_app, "ANIMAL_ID_API_ORIGIN", "https://id.example.ts.net"
    )
    html = site_app.render_identify_page()
    assert 'data-api-origin="https://id.example.ts.net"' in html


def test_pages_do_not_advertise_ai_generated_copy():
    for markup in (
        render_page(),
        render_about_page(),
        render_moments_page(),
        render_identify_page(),
    ):
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
    assert 'id="diagnostics-pressure"' in html
    assert 'id="diagnostics-daylight"' in html
    assert 'id="diagnostics-memory"' in html
    assert 'id="diagnostics-load"' in html
    assert 'id="diagnostics-processes"' in html
    assert 'id="temperature-unit-toggle"' in html
    assert 'aria-pressed="true"' in html
    assert 'data-temperature-unit="f"' in html
    assert html.count('class="diagnostics-help"') == 8
    assert html.count('tabindex="0"') >= 8
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
    assert "pressure" in source
    assert "pressureHpa" in source
    assert "daylight" in source
    assert "data?.climate" in source
    assert "celsiusToFahrenheit" in source
    assert "temperatureUnit" in source
    assert 'dataset.temperatureUnit' in source
    assert 'Not connected' in source


def test_pages_declare_the_favicon():
    for markup in (
        render_page(),
        render_about_page(),
        render_moments_page(),
        render_identify_page(),
    ):
        assert '/assets/favicon.svg' in markup, "page is missing the tab icon"
        assert 'type="image/svg+xml"' in markup, "favicon type hint is missing"


def test_every_page_initializes_the_registered_firebase_analytics_app():
    for markup in (
        render_page(),
        render_about_page(),
        render_moments_page(),
        render_identify_page(),
    ):
        assert 'src="/assets/analytics.js"' in markup
        assert 'type="module"' in markup

    source = (WEB_ROOT / "static" / "analytics.js").read_text()
    assert "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js" in source
    assert "https://www.gstatic.com/firebasejs/12.18.0/firebase-analytics.js" in source
    assert 'measurementId: "G-WMSVQJWJQR"' in source
    assert "initializeApp(firebaseConfig)" in source
    assert "getAnalytics(app)" in source
    assert "logEvent" in source
    assert "owlcamTrack" in source
    assert 'navigator.doNotTrack === "1"' in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_every_page_has_an_accessible_admin_login_and_panel():
    for markup in (
        render_page(),
        render_about_page(),
        render_moments_page(),
        render_identify_page(),
    ):
        assert 'id="admin-open"' in markup
        assert 'id="theme-toggle"' in markup
        assert 'href="#main-content"' in markup
        assert 'id="main-content"' in markup
        assert 'aria-label="Open admin sign-in for station controls"' in markup
        assert 'id="admin-dialog"' in markup
        assert 'id="admin-login-form"' in markup
        assert 'autocomplete="username"' in markup
        assert 'autocomplete="current-password"' in markup
        assert 'id="admin-dashboard"' in markup
        assert 'id="admin-stream-toggle"' in markup
        assert 'class="admin-feed-grid"' in markup
        assert 'aria-describedby="admin-panel-desc"' in markup
        assert 'id="admin-log-output"' in markup
        assert 'id="admin-firebase-status"' in markup
        assert "Analytics is not configured" not in markup
        assert "Open visitor analytics" in markup
        assert 'src="/assets/admin.js"' in markup


def test_admin_client_uses_cookie_sessions_csrf_and_safe_text_rendering():
    source = (WEB_ROOT / "static" / "admin.js").read_text()

    assert 'const API = "/admin/api"' in source
    assert 'credentials: "same-origin"' in source
    assert '"X-Owlcam-Csrf": csrfToken' in source
    assert 'api("/session"' in source
    assert 'api("/stream"' in source
    assert "`/logs?service=${encodeURIComponent(" in source
    assert 'api("/firebase"' in source
    assert ".textContent =" in source
    assert ".innerHTML" not in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "confirm(" not in source
    assert 'setAttribute("aria-pressed"' in source
    assert "setFeedControl" in source


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


def test_player_can_switch_between_nest_and_usb_streams():
    source = (WEB_ROOT / "static" / "player.js").read_text()

    assert "owlcamStreamPath" in source
    assert "sessionStorage" in source
    assert "data-camera-source" in source
    assert "/owl2/index.m3u8" in source or "streamUrlUsb" in source


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
    assert (output / "identify.html").is_file()
    assert (output / "moments.html").is_file()
    assert (output / "assets" / "chris-carver.webp").is_file()
    assert (output / "assets" / "moments" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "nest-box-build.jpg").is_file()
    assert (output / "assets" / "moments" / "thumbs" / "mole-delivery.jpg").is_file()
    assert (output / "assets" / "moments" / "mole-delivery.webm").is_file()
    assert not (output / "assets" / "moments" / "winter-watch.jpg").exists()
    index = (output / "index.html").read_text()
    about = (output / "about.html").read_text()
    identify = (output / "identify.html").read_text()
    moments = (output / "moments.html").read_text()
    assert 'data-stream-url="/owl/index.m3u8"' in index
    assert "Checking private feed" not in index

    # An absolute camera host is the whole bug: it resolves to a private
    # address on Tailscale devices and the browser blocks the request.
    for page in (index, about, moments, identify):
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
    assert not (assets / "moments-live.js").exists()
    assert not (assets / "moments-calendar.js").exists()
    assert not (assets / "admin.js").exists()
    assert not (assets / "home-status.js").exists()
    assert not (assets / "identify.js").exists()
    assert not (assets / "analytics.js").exists()
    assert not (assets / "theme.js").exists()

    hashed = {p.name for p in assets.glob("*.*.css")} | {
        p.name for p in assets.glob("*.*.js")
    }
    assert any(n.startswith("styles.") and n.endswith(".css") for n in hashed)
    assert any(n.startswith("player.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("diagnostics.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("moments.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("admin.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("home-status.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("identify.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("analytics.") and n.endswith(".js") for n in hashed)
    assert any(n.startswith("theme.") and n.endswith(".js") for n in hashed)

    index = (output / "index.html").read_text()
    assert '"/assets/styles.css"' not in index
    referenced = [n for n in hashed if f"/assets/{n}" in index]
    assert sorted(referenced) == sorted(
        n
        for n in hashed
        if n.startswith(
            (
                "styles.",
                "player.",
                "diagnostics.",
                "home-status.",
                "admin.",
                "analytics.",
                "theme.",
            )
        )
    )

    # A content change must produce a different URL.
    first = {n for n in hashed if n.startswith("styles.")}
    (WEB_ROOT / "static" / "styles.css").read_text()
    second_output = tmp_path / "public2"
    build_site(second_output)
    again = {p.name for p in (second_output / "assets").glob("styles.*.css")}
    assert first == again, "identical input produced an unstable fingerprint"
