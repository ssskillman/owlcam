from fasthtml.common import (
    A,
    Body,
    Button,
    Details,
    Dialog,
    Div,
    Footer,
    Form,
    H1,
    H2,
    Head,
    Header,
    Html,
    Img,
    Input,
    Label,
    Link,
    Main,
    Meta,
    Nav,
    NotStr,
    Option,
    P,
    Pre,
    Script,
    Section,
    Select,
    Small,
    Span,
    Strong,
    Summary,
    Title,
    Ul,
    Video,
    to_xml,
)
import os

# Relative on purpose. The Pi serves this page beside the stream, so both come
# from one origin and the browser has no cross-origin request to block. Naming
# an absolute host here reintroduces exactly that: on any device running
# Tailscale, MagicDNS resolves the Pi to a private address and the browser
# refuses a public page access to the local address space, killing the video and
# the vitals together.
DEFAULT_STREAM_URL = "/owl/index.m3u8"
DEFAULT_USB_STREAM_URL = "/owl2/index.m3u8"
DEFAULT_DIAGNOSTICS_URL = "/diagnostics"
ANIMAL_ID_API_ORIGIN = os.environ.get("ANIMAL_ID_API_ORIGIN", "").rstrip("/")
OWLCAM_GROUP_URL = "https://www.facebook.com/groups/619431688614242/"
MOMENTS = (
    {
        "filename": "nest-box-build.jpg",
        "timestamp": "2026-08-29",
        "type": "photo",
        "badge": "NEST ARCHIVE",
        "subject": "The box itself",
        "alt": (
            "Hand-built owl-shaped nest box on a porch rail at night, with "
            "camera lenses set into its eyes"
        ),
        "story": (
            "Before any owl moved in, the nest box sat on the porch rail "
            "with lenses set into its eyes—an owl built to watch owls. "
            "Layered shingle feathers, a driftwood perch, and a doorway "
            "sized for a barred owl family."
        ),
        "credit": "Shared in the OwlCam group",
        "source": OWLCAM_GROUP_URL,
    },
    {
        "filename": "owlet-in-doorway.jpg",
        "timestamp": "2026-08-29",
        "type": "photo",
        "badge": "NEST ARCHIVE",
        "subject": "Chick in the doorway",
        "alt": "Downy owlet looking out of the owl-shaped nest box doorway",
        "story": (
            "A downy chick fills the doorway, still mostly fluff, watching "
            "woods it has not flown yet. Behind it the camera housing sits "
            "back in the dark of the box—the same vantage the live feed "
            "carries."
        ),
        "credit": "Shared in the OwlCam group",
        "source": OWLCAM_GROUP_URL,
    },
    {
        "filename": "owlet-on-ledge.jpg",
        "timestamp": "2026-08-29",
        "type": "photo",
        "badge": "NEST ARCHIVE",
        "subject": "Standing tall",
        "alt": "Owlet standing on the front ledge of the nest box in daylight",
        "story": (
            "Up on the front ledge, wings tucked, the owlet practices being "
            "a whole owl. Branching like this comes before real flight, and "
            "it is when a parent's food runs are hardest to keep up with."
        ),
        "credit": "Shared in the OwlCam group",
        "source": OWLCAM_GROUP_URL,
    },
    {
        "filename": "adult-barred-owl.jpg",
        "timestamp": "2026-08-29",
        "type": "photo",
        "badge": "NEST ARCHIVE",
        "subject": "The parent",
        "alt": "Adult barred owl perched on a branch in green summer canopy",
        "story": (
            "The adult keeps station in the canopy: dark eyes, barred "
            "chest, no sound at all. This is the bird the box was built "
            "for, and the one whose comings and goings make a whole night "
            "worth watching."
        ),
        "credit": "Shared in the OwlCam group",
        "source": OWLCAM_GROUP_URL,
    },
    {
        "filename": "mole-delivery.webm",
        "timestamp": "2013-07-21",
        "type": "video",
        "badge": "PLACEHOLDER CLIP",
        "subject": "Food",
        "alt": "Barred owl eating a mole",
        "story": (
            "A mole becomes a hard-won meal. When OwlCam catches food "
            "arriving at the box, the clues—prey, parent, time, and which "
            "chick eats first—can turn a few seconds into a family story."
        ),
        "credit": "Mike · CC BY 2.0",
        "source": (
            "https://commons.wikimedia.org/wiki/"
            "File:Barred_owl_(Strix_varia)_dining_on_a_mole.webm"
        ),
        "license": "https://creativecommons.org/licenses/by/2.0",
    },
)


def _diagnostic_metric(
    label: str,
    metric_id: str,
    explanation: str,
) -> Div:
    help_id = f"{metric_id}-help"
    return Div(
        Span(label, cls="diagnostics-key"),
        P("—", id=metric_id),
        Span(explanation, id=help_id, role="tooltip", cls="diagnostics-help"),
        cls="diagnostics-metric",
        tabindex="0",
        aria_describedby=help_id,
    )


def _head(*, title: str, description: str, include_player: bool, include_identify: bool = False) -> Head:
    scripts = [
        Script(src="/assets/admin.js", defer=True),
        Script(src="/assets/analytics.js", type="module"),
    ]
    if include_identify:
        scripts = [Script(src="/assets/identify.js", defer=True), *scripts]
    if include_player:
        scripts = [
            Script(
                src="https://cdn.jsdelivr.net/npm/hls.js@1.7.1/dist/hls.min.js",
                defer=True,
                integrity=(
                    "sha384-X6qxWXYhVZFp6V31bNDBz4eOoPnZloPbOdTcnhnv"
                    "RJY2+2pDMrO7R4/1mXfJ9VXY"
                ),
                crossorigin="anonymous",
            ),
            Script(src="/assets/player.js", defer=True),
            Script(src="/assets/diagnostics.js", defer=True),
            Script(src="/assets/home-status.js", defer=True),
            *scripts,
        ]
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=description),
        Title(title),
        Link(rel="icon", href="/assets/favicon.svg", type="image/svg+xml"),
        Link(rel="preconnect", href="https://cdn.jsdelivr.net"),
        Link(rel="stylesheet", href="/assets/styles.css"),
        *scripts,
    )


def _nav(*, active: str) -> Div:
    home = {"aria_current": "page"} if active == "live" else {}
    identify = {"aria_current": "page"} if active == "identify" else {}
    moments = {"aria_current": "page"} if active == "moments" else {}
    about = {"aria_current": "page"} if active == "about" else {}
    return Div(
        Div(
            A("CARVER FIELD STATION", href="/", cls="eyebrow", **home),
            P(
                "",
                id="nav-signed-in",
                cls="nav-signed-in",
                hidden=True,
            ),
            cls="site-brand",
        ),
        Nav(
            A("Upload & Identify", href="/identify", **identify),
            A("Moments", href="/moments", **moments),
            A("About", href="/about", **about),
            Button(
                "?",
                type="button",
                id="admin-open",
                cls="admin-open",
                aria_label="Open admin login",
            ),
            cls="site-nav",
            aria_label="Site",
        ),
        cls="utility-bar",
    )


def _admin_panel() -> Dialog:
    return Dialog(
        Header(
            Div(
                Span("FIELD STATION CONTROL", cls="admin-kicker"),
                H2("OwlCam admin", id="admin-panel-title"),
            ),
            Button(
                "Close",
                type="button",
                id="admin-close",
                cls="admin-close",
                aria_label="Close admin panel",
            ),
            cls="admin-header",
        ),
        Div(
            P(
                "Sign in to inspect services, read bounded logs, and control "
                "the camera feed.",
                cls="admin-intro",
            ),
            Form(
                Label("Username", fr="admin-username"),
                Input(
                    id="admin-username",
                    name="username",
                    value="ccarver",
                    autocomplete="username",
                    maxlength="64",
                    required=True,
                ),
                Label("Password", fr="admin-password"),
                Input(
                    id="admin-password",
                    name="password",
                    type="password",
                    autocomplete="current-password",
                    maxlength="1024",
                    required=True,
                ),
                Button("Sign in", type="submit"),
                id="admin-login-form",
                cls="admin-login-form",
            ),
            P(
                "",
                id="admin-login-status",
                cls="admin-message",
                role="status",
                aria_live="polite",
            ),
            id="admin-login",
        ),
        Div(
            Div(
                Div(
                    Span("SYSTEM STATE", cls="admin-kicker"),
                    Strong("Loading…", id="admin-overall-status"),
                ),
                Div(
                    Button(
                        "Refresh",
                        type="button",
                        id="admin-refresh",
                        cls="admin-secondary",
                    ),
                    Button(
                        "Sign out",
                        type="button",
                        id="admin-logout",
                        cls="admin-secondary",
                    ),
                    cls="admin-actions",
                ),
                cls="admin-toolbar",
            ),
            Section(
                Div(
                    Span("LIVE VIDEO", cls="admin-kicker"),
                    H2("Nest camera (CSI)"),
                    P("Checking the stream unit…", id="admin-stream-state"),
                    cls="admin-control-copy",
                ),
                Button(
                    "Turn feed off",
                    type="button",
                    id="admin-stream-toggle",
                    cls="admin-danger",
                    disabled=True,
                ),
                cls="admin-control",
                aria_label="Nest camera stream control",
            ),
            Section(
                Div(
                    Span("LIVE VIDEO", cls="admin-kicker"),
                    H2("USB camera"),
                    P("Checking the USB stream unit…", id="admin-stream-usb-state"),
                    cls="admin-control-copy",
                ),
                Button(
                    "Turn USB feed off",
                    type="button",
                    id="admin-stream-usb-toggle",
                    cls="admin-danger",
                    disabled=True,
                ),
                cls="admin-control",
                aria_label="USB camera stream control",
            ),
            Section(
                H2("Services"),
                Div(id="admin-services", cls="admin-service-grid"),
                cls="admin-section",
            ),
            Section(
                H2("Pi health"),
                Div(id="admin-host-status", cls="admin-metric-grid"),
                cls="admin-section",
            ),
            Section(
                H2("Firebase edge"),
                P(
                    "Checking redirect health…",
                    id="admin-firebase-status",
                    cls="admin-firebase",
                ),
                Small(
                    "Redirect health is shown here. Visitor counts and page "
                    "activity live in the linked GA4 property."
                ),
                P(
                    A(
                        "Open visitor analytics",
                        href=(
                            "https://console.firebase.google.com/project/"
                            "carver-owlcam-72343/analytics"
                        ),
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    cls="admin-analytics-link",
                ),
                cls="admin-section",
            ),
            Section(
                Div(
                    H2("Service logs"),
                    Div(
                        Label("Unit", fr="admin-log-service"),
                        Select(
                            Option("Nest stream", value="stream"),
                            Option("USB stream", value="streamUsb"),
                            Option("MediaMTX", value="media"),
                            Option("Site", value="site"),
                            Option("Diagnostics", value="diagnostics"),
                            Option("Admin", value="admin"),
                            id="admin-log-service",
                        ),
                        Button(
                            "Load logs",
                            type="button",
                            id="admin-load-logs",
                            cls="admin-secondary",
                        ),
                        cls="admin-log-controls",
                    ),
                    cls="admin-section-heading",
                ),
                Pre(
                    "Choose a service to load its latest 100 journal lines.",
                    id="admin-log-output",
                    tabindex="0",
                ),
                cls="admin-section admin-logs",
            ),
            P(
                "",
                id="admin-action-status",
                cls="admin-message",
                role="status",
                aria_live="polite",
            ),
            id="admin-dashboard",
            hidden=True,
        ),
        id="admin-dialog",
        cls="admin-dialog",
        aria_labelledby="admin-panel-title",
    )


def _footer() -> Footer:
    return Footer(
        P(
            "CARVER OWLCAM",
            Span(" · ", aria_hidden="true"),
            A("View the project", href="https://github.com/ssskillman/owlcam"),
        ),
        P("Observe quietly. Protect the habitat."),
    )


def render_page(
    stream_url: str = DEFAULT_STREAM_URL,
    usb_stream_url: str = DEFAULT_USB_STREAM_URL,
) -> str:
    page = Html(
        _head(
            title="Carver OwlCam — Live from the Nest",
            description="A private live look inside the Carver owl nest.",
            include_player=True,
        ),
        Body(
            _nav(active="live"),
            Div(
                Div(
                    Img(
                        src="/assets/icons/numbers/1.png",
                        alt="",
                        id="capture-toast-icon",
                        cls="capture-toast-number",
                        width="24",
                        height="24",
                        decoding="async",
                        hidden=True,
                    ),
                    Span(
                        "0",
                        id="capture-toast-count",
                        cls="capture-toast-count-text",
                        hidden=True,
                    ),
                    cls="capture-toast-count-wrap",
                ),
                P("nest captures · last 24h", cls="capture-toast-copy"),
                id="capture-toast",
                cls="capture-toast",
                role="status",
                aria_live="polite",
                hidden=True,
            ),
            _admin_panel(),
            Main(
                Section(
                    Div(
                        Div(
                            Span("●", aria_hidden="true"),
                            " LIVE HABITAT CAMERA",
                            cls="live-label",
                        ),
                        H1("Quiet hours.", Span("Wild lives.", cls="accent")),
                        P(
                            "A window into the nest box—streamed from a tiny "
                            "Raspberry Pi at the edge of the woods.",
                            cls="lede",
                        ),
                        cls="intro",
                    ),
                    Div(
                        Div(
                            Video(
                                id="owlcam-player",
                                controls=True,
                                autoplay=True,
                                muted=True,
                                playsinline=True,
                                preload="metadata",
                                aria_label="Carver OwlCam livestream",
                                data_stream_url=stream_url,
                                data_stream_url_usb=usb_stream_url,
                            ),
                            Div(
                                Div("◉", cls="owl-mark", aria_hidden="true"),
                                # A resting camera and an unreachable one look
                                # identical from the couch, so the panel starts
                                # on the state that is actually true — connecting
                                # — and player.js names the real cause once it
                                # knows it.
                                H2("Connecting to the camera", id="offline-title"),
                                P(
                                    "Contacting the nest box. This usually "
                                    "takes a few seconds.",
                                    id="offline-message",
                                ),
                                Button(
                                    "Try again",
                                    id="retry-stream",
                                    type="button",
                                ),
                                id="offline-panel",
                                cls="offline-panel",
                            ),
                            cls="video-stage",
                        ),
                        Div(
                            Div(
                                Span(cls="status-dot", aria_hidden="true"),
                                Span(
                                    "Checking live feed…",
                                    id="stream-status",
                                    aria_live="polite",
                                ),
                                cls="status",
                            ),
                            Div(
                                Button(
                                    "Nest cam",
                                    type="button",
                                    cls="camera-source",
                                    data_camera_source="nest",
                                    aria_pressed="true",
                                ),
                                Button(
                                    "USB cam",
                                    type="button",
                                    cls="camera-source",
                                    data_camera_source="usb",
                                    aria_pressed="false",
                                ),
                                id="camera-source-toggle",
                                cls="camera-toggle",
                                role="group",
                                aria_label="Live camera source",
                            ),
                            Small(
                                "Nest 1920×1080 · USB 1280×720 · H.264",
                                id="player-format-label",
                            ),
                            cls="player-meta",
                        ),
                        cls="player-shell",
                    ),
                    cls="hero",
                ),
                Section(
                    Div(
                        Div(
                            Span("LIVE SYSTEM DIAGNOSTICS", cls="diagnostics-label"),
                            H2("Nest box vitals"),
                        ),
                        Div(
                            Div(
                                Button(
                                    "°F",
                                    type="button",
                                    cls="temperature-unit",
                                    data_temperature_unit="f",
                                    aria_pressed="true",
                                ),
                                Button(
                                    "°C",
                                    type="button",
                                    cls="temperature-unit",
                                    data_temperature_unit="c",
                                    aria_pressed="false",
                                ),
                                id="temperature-unit-toggle",
                                cls="temperature-toggle",
                                role="group",
                                aria_label="Temperature unit",
                            ),
                            Div(
                                Span(cls="diagnostics-dot", aria_hidden="true"),
                                Span(
                                    "Connecting to the Pi…",
                                    id="diagnostics-status",
                                    aria_live="polite",
                                ),
                                cls="diagnostics-state",
                            ),
                            cls="diagnostics-controls",
                        ),
                        cls="diagnostics-header",
                    ),
                    Div(
                        Span("NEST CONDITIONS", cls="diagnostics-row-label"),
                        Div(
                            _diagnostic_metric(
                                "NEST AIR",
                                "diagnostics-habitat-temperature",
                                "Air temperature shapes how easily adults and "
                                "hatchlings regulate body heat. Watch trends; "
                                "do not disturb the nest to chase a single reading.",
                            ),
                            _diagnostic_metric(
                                "RELATIVE HUMIDITY",
                                "diagnostics-humidity",
                                "Humidity adds context for damp bedding, mold risk, "
                                "and heat stress. Outdoor nests naturally swing "
                                "through a wide range.",
                            ),
                            _diagnostic_metric(
                                "BAROMETRIC PRESSURE",
                                "diagnostics-pressure",
                                "Pressure helps track weather fronts and altitude "
                                "context for the nest site. It is independent of "
                                "the camera enclosure.",
                            ),
                            _diagnostic_metric(
                                "DAYLIGHT",
                                "diagnostics-daylight",
                                "Light level marks the day/night rhythm that drives "
                                "owl activity and camera night mode. A future lux "
                                "sensor will provide this reading.",
                            ),
                            cls="diagnostics-row diagnostics-row-habitat",
                        ),
                        Span("PI HEALTH", cls="diagnostics-row-label"),
                        Div(
                            _diagnostic_metric(
                                "PI TEMPERATURE",
                                "diagnostics-temperature",
                                "The processor temperature is not the nest "
                                "temperature. It warns when the camera computer may "
                                "throttle or stop streaming.",
                            ),
                            _diagnostic_metric(
                                "MEMORY AVAILABLE",
                                "diagnostics-memory",
                                "Free working memory helps the Pi encode and serve "
                                "video without interruption.",
                            ),
                            _diagnostic_metric(
                                "1-MINUTE LOAD",
                                "diagnostics-load",
                                "Recent processor demand. Sustained high load can "
                                "make the live view stutter or fall behind.",
                            ),
                            _diagnostic_metric(
                                "STREAMING PROCESSES",
                                "diagnostics-processes",
                                "The camera, encoder, and media server must all be "
                                "running for observers to watch without approaching "
                                "the nest.",
                            ),
                            cls="diagnostics-row diagnostics-row-system",
                        ),
                        cls="diagnostics-groups",
                    ),
                    Small("Waiting for first sample", id="diagnostics-updated"),
                    id="diagnostics",
                    cls="diagnostics",
                    data_diagnostics_url=DEFAULT_DIAGNOSTICS_URL,
                    aria_label="Realtime OwlCam system diagnostics",
                ),
                Section(
                    Div(
                        Span("01", cls="fact-number"),
                        H2("Edge powered"),
                        P(
                            "The Pi handles capture and encoding locally, "
                            "keeping the nest camera resilient."
                        ),
                        cls="fact",
                    ),
                    Div(
                        Span("02", cls="fact-number"),
                        H2("One door in"),
                        P(
                            "Tailscale publishes a single HTTPS address. No "
                            "camera ports, logins, or accounts are exposed."
                        ),
                        cls="fact",
                    ),
                    Div(
                        Span("03", cls="fact-number"),
                        H2("Night watch"),
                        P(
                            "Built for the question every morning: what "
                            "happened in the nest last night?"
                        ),
                        cls="fact",
                    ),
                    cls="facts",
                    aria_label="About OwlCam",
                ),
            ),
            _footer(),
            data_api_origin=ANIMAL_ID_API_ORIGIN,
        ),
        lang="en",
    )
    return to_xml(page)


# Inline so the progress owl costs no extra request and can inherit the theme
# colours. Wings come first so the body paints over their hinges.
IDENTIFY_OWL_SVG = """
<svg class="identify-owl" viewBox="0 0 96 64" width="64" height="43" focusable="false">
  <g class="identify-owl-wing identify-owl-wing-left">
    <path class="identify-owl-body"
          d="M41 27C35 21 28 17 20 17C13 17 7 20 3 25C6 27 9 28 13 28C10 30 7 32 4 33C11 35 19 34 26 31C25 34 22 36 19 38C28 39 37 35 43 29Z" />
    <path class="identify-owl-quill" d="M19 22C24 26 30 29 35 31" />
  </g>
  <g class="identify-owl-wing identify-owl-wing-right">
    <path class="identify-owl-body"
          d="M55 27C61 21 68 17 76 17C83 17 89 20 93 25C90 27 87 28 83 28C86 30 89 32 92 33C85 35 77 34 70 31C71 34 74 36 77 38C68 39 59 35 53 29Z" />
    <path class="identify-owl-quill" d="M77 22C72 26 66 29 61 31" />
  </g>
  <path class="identify-owl-body" d="M42 50L43 58C46 60 50 60 53 58L54 50Z" />
  <path class="identify-owl-body"
        d="M48 26C40 26 36 33 36 40C36 47 41 52 48 54C55 52 60 47 60 40C60 33 56 26 48 26Z" />
  <path class="identify-owl-body" d="M37 12C35 8 34 5 34 2C38 4 41 7 43 10Z" />
  <path class="identify-owl-body" d="M59 12C61 8 62 5 62 2C58 4 55 7 53 10Z" />
  <path class="identify-owl-body"
        d="M48 7C41 7 35 13 35 21C35 29 41 34 48 34C55 34 61 29 61 21C61 13 55 7 48 7Z" />
  <path class="identify-owl-face"
        d="M48 14C46.5 11.5 42 12.5 40 15.5C37.5 18.5 37.5 24.5 40 27.5C42 30 46.5 30.5 48 28.5C49.5 30.5 54 30 56 27.5C58.5 24.5 58.5 18.5 56 15.5C54 12.5 49.5 11.5 48 14Z" />
  <circle class="identify-owl-eye" cx="43" cy="21" r="3.9" />
  <circle class="identify-owl-eye" cx="53" cy="21" r="3.9" />
  <circle class="identify-owl-glint" cx="44.3" cy="19.7" r="1.2" />
  <circle class="identify-owl-glint" cx="54.3" cy="19.7" r="1.2" />
  <path class="identify-owl-beak" d="M48 24.5L45.8 29.5H50.2Z" />
</svg>
"""


def render_identify_page() -> str:
    page = Html(
        _head(
            title="What animal did you spot? — Carver OwlCam",
            description=(
                "Upload a wildlife photo and OwlCam will help identify "
                "the animal."
            ),
            include_player=False,
            include_identify=True,
        ),
        Body(
            _nav(active="identify"),
            _admin_panel(),
            Main(
                Section(
                    Div(
                        Span("COMMUNITY", cls="live-label"),
                        H1("What animal ", Span("did you spot?", cls="accent")),
                        P(
                            "Upload a photo from your yard, trail camera, or "
                            "neighborhood and OwlCam will help identify the "
                            "animal. Clear photos with one animal work best.",
                            cls="lede",
                        ),
                        cls="identify-intro",
                    ),
                    Form(
                        Label("Wildlife photos", fr="identify-files", cls="sr-only"),
                        Input(
                            type="file",
                            id="identify-files",
                            name="images",
                            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp",
                            multiple=True,
                        ),
                        Div(
                            P(
                                "Drop JPG, PNG, or WebP photos here, or choose "
                                "files. Up to 5 photos, 10 MB each."
                            ),
                            Small(
                                "Only JPG, PNG, and WebP image files are accepted. "
                                "Non-image and malformed uploads are rejected.",
                                cls="identify-file-policy",
                            ),
                            Button(
                                "Choose photos",
                                type="button",
                                id="identify-browse",
                            ),
                            id="identify-drop",
                            cls="identify-drop",
                            tabindex="0",
                            role="button",
                            aria_label="Drop photos or choose files",
                        ),
                        Details(
                            Summary(
                                "Selected photos",
                                id="identify-selection-summary",
                            ),
                            Ul(id="identify-thumbs", cls="identify-thumbs"),
                            id="identify-selection",
                            cls="identify-selection",
                            open=True,
                            hidden=True,
                        ),
                        Button(
                            "Identify animals",
                            type="submit",
                            id="identify-submit",
                        ),
                        P("", id="identify-status", aria_live="polite"),
                        Div(
                            NotStr(IDENTIFY_OWL_SVG),
                            id="identify-loader",
                            cls="identify-loader",
                            hidden=True,
                            aria_hidden="true",
                        ),
                        data_api_origin=ANIMAL_ID_API_ORIGIN,
                        id="identify-form",
                        cls="identify-form",
                    ),
                    Section(
                        H2("Animals identified"),
                        P(
                            Strong("0", id="identify-summary-total"),
                            Span(
                                " animals identified so far",
                                id="identify-summary-total-label",
                            ),
                            cls="identify-summary-total",
                            aria_live="polite",
                        ),
                        P(
                            "Select an animal group to see the species.",
                            cls="identify-summary-hint",
                        ),
                        Div(id="identify-chart", cls="identify-chart"),
                        id="identify-summary",
                        cls="identify-summary",
                        hidden=True,
                    ),
                    P(
                        "Identification is generated by an AI wildlife model "
                        "and may be incorrect.",
                        id="identify-results-disclaimer",
                        cls="identify-disclaimer",
                        hidden=True,
                    ),
                    Div(id="identify-results", cls="identify-results"),
                    cls="identify-page",
                )
            ),
            _footer(),
        ),
        lang="en",
    )
    return to_xml(page)


def render_about_page() -> str:
    page = Html(
        _head(
            title="About Chris Carver — Carver OwlCam",
            description=(
                "Meet Chris Carver, Eagle Scout, AMG co-owner, and the "
                "neighbor sharing OwlCam with anyone who loves the outdoors."
            ),
            include_player=False,
        ),
        Body(
            _nav(active="about"),
            _admin_panel(),
            Main(
                Section(
                    Div(
                        Span("ABOUT", cls="live-label"),
                        H1("Chris Carver.", Span("Good dude.", cls="accent")),
                        P(
                            "This nest camera exists so friends, family, and "
                            "anyone who will linger a minute can share a quiet "
                            "look at the woods with Chris. Enjoy his love of "
                            "nature. Share the OwlCam moments with him.",
                            cls="lede",
                        ),
                    ),
                    Div(
                        Img(
                            src="/assets/chris-carver.webp",
                            alt="Chris Carver outdoors by a pool",
                            width="750",
                            height="562",
                            decoding="async",
                        ),
                        cls="about-portrait",
                    ),
                    cls="about-intro",
                ),
                Section(
                    Div(
                        H2("Outdoors, always"),
                        P(
                            "Chris is an Eagle Scout who still shares the "
                            "outdoors with family and with anyone who will "
                            "chat. He grew up in North Raleigh, found the "
                            "water at Seven Oaks Swim Club on Creedmoor "
                            "Road, joined the swim team, and spent summers "
                            "asking the lifeguards every question he could "
                            "think of."
                        ),
                        P(
                            "Through youth he was deep in Boy Scouts. Just "
                            "before Eagle, he earned BSA Lifeguard. In "
                            "summer 2000, at 15, he joined the aquatics "
                            "staff at Camp Raven Knob in the North Carolina "
                            "foothills. He stayed four summers, teaching "
                            "swimming and lifesaving merit badges."
                        ),
                        cls="about-copy",
                    ),
                    Div(
                        H2("Builder of pools, and of this nest watch"),
                        P(
                            "While at NC State University he managed the "
                            "Brier Creek Country Club pool for three "
                            "summers, then co-founded Aquatic Management "
                            "Group. He is Chief Service Officer and owner—"
                            "designer, engineer, mechanic, contractor, and "
                            "craftsman on the job, and a good neighbor off it."
                        ),
                        P(
                            "He is an excellent father, a loud cheerleader "
                            "at kids’ sports, a pool designer who still "
                            "gets his hands dirty, and a reliable jokester. "
                            "In spare hours he looks for the elusive North "
                            "Carolina record bass. All around, a good dude "
                            "to know."
                        ),
                        cls="about-copy",
                    ),
                    cls="about-grid",
                    aria_label="About Chris Carver",
                ),
            ),
            _footer(),
        ),
        lang="en",
    )
    return to_xml(page)


def _moment_media(item: dict[str, str]):
    """Grid rows load a small thumbnail; the original opens on demand."""
    stem = item["filename"].rsplit(".", 1)[0]
    thumbnail = f"/assets/moments/thumbs/{stem}.jpg"

    if item["type"] == "video":
        return Video(
            src=f"/assets/moments/{item['filename']}",
            poster=thumbnail,
            controls=True,
            muted=True,
            playsinline=True,
            preload="none",
            aria_label=item["alt"],
        )

    return A(
        Img(
            src=thumbnail,
            alt=item["alt"],
            loading="lazy",
            decoding="async",
        ),
        Span("View full size", cls="thumb-hint"),
        href=f"/assets/moments/{item['filename']}",
        cls="moment-thumb",
    )


def _moment_card(item: dict[str, str]) -> Div:
    media = _moment_media(item)
    credit = [
        "Media: ",
        A(item["credit"], href=item["source"], rel="noopener noreferrer"),
    ]
    if "license" in item:
        credit += [
            " · ",
            A("license", href=item["license"], rel="noopener noreferrer"),
        ]
    return Div(
        Div(
            media,
            Span(item["badge"], cls="placeholder-badge"),
            cls="moment-media",
        ),
        Div(
            Div(
                Span(item["type"].upper(), cls="moment-type"),
                Span(item["timestamp"]),
                cls="moment-kicker",
            ),
            H2(item["subject"]),
            P(item["story"], cls="moment-story"),
            P(
                Span("FIELD NOTE", cls="story-label"),
                " · ",
                item["filename"],
                cls="moment-file",
            ),
            P(*credit, cls="moment-credit"),
            cls="moment-copy",
        ),
        cls="moment-card",
        data_filename=item["filename"],
        data_timestamp=item["timestamp"],
        data_type=item["type"],
        data_subject=item["subject"],
    )


def render_moments_page() -> str:
    page = Html(
        _head(
            title="Owl Moments — Carver OwlCam",
            description=(
                "A sortable field log of OwlCam action shots and short clips "
                "from the barred owl nest."
            ),
            include_player=False,
        ),
        Body(
            _nav(active="moments"),
            _admin_panel(),
            Main(
                Section(
                    Span("FIELD LOG", cls="live-label"),
                    H1("Small moments.", Span("Wild stories.", cls="accent")),
                    P(
                        "Action shots and short clips from the nest box—each "
                        "with a field note about parents, food deliveries, "
                        "chicks, and movement in the box.",
                        cls="lede",
                    ),
                    P(
                        "Nest archive photos come from the OwlCam group; "
                        "their original capture dates were not preserved in "
                        "the shared files, so timestamps show when each was "
                        "logged here. The clip marked placeholder is licensed "
                        "stock standing in until OwlCam records its own video.",
                        cls="moments-notice",
                    ),
                    cls="moments-intro",
                ),
                Section(
                    Span("LIVE FROM THE NEST", cls="live-label"),
                    H2("From the nest."),
                    P(
                        "Automatic captures from the live nest camera, "
                        "classified when something recognizable is in frame. "
                        "This section refreshes about every thirty seconds "
                        "while the photo-processing server is online.",
                        cls="lede nest-moments-lede",
                    ),
                    P(
                        "Loading recent nest captures…",
                        id="nest-moments-status",
                        cls="nest-moments-status",
                        aria_live="polite",
                    ),
                    Div(
                        id="nest-moments-grid",
                        cls="moments-grid nest-moments-grid",
                    ),
                    cls="nest-moments",
                    data_api_origin=ANIMAL_ID_API_ORIGIN,
                ),
                Section(
                    Div(
                        Span("SORT FIELD LOG", cls="sort-title"),
                        Button(
                            "Filename",
                            type="button",
                            data_sort_key="filename",
                            aria_pressed="false",
                        ),
                        Button(
                            "Timestamp",
                            type="button",
                            data_sort_key="timestamp",
                            aria_pressed="true",
                        ),
                        Button(
                            "Media type",
                            type="button",
                            data_sort_key="type",
                            aria_pressed="false",
                        ),
                        Button(
                            "Subject",
                            type="button",
                            data_sort_key="subject",
                            aria_pressed="false",
                        ),
                        cls="sort-header",
                        aria_label="Sort moments",
                    ),
                    P(
                        "Sorted by timestamp, newest first.",
                        id="sort-status",
                        cls="sort-status",
                        aria_live="polite",
                    ),
                    Div(
                        *(_moment_card(item) for item in MOMENTS),
                        id="moments-grid",
                        cls="moments-grid",
                    ),
                    cls="moments-log",
                ),
            ),
            _footer(),
            Script(src="/assets/moments-live.js", defer=True),
            Script(src="/assets/moments.js", defer=True),
        ),
        lang="en",
    )
    return to_xml(page)
