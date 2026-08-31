from fasthtml.common import (
    A,
    Body,
    Button,
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
    Option,
    P,
    Pre,
    Script,
    Section,
    Select,
    Small,
    Span,
    Strong,
    Title,
    Video,
    to_xml,
)

# Relative on purpose. The Pi serves this page beside the stream, so both come
# from one origin and the browser has no cross-origin request to block. Naming
# an absolute host here reintroduces exactly that: on any device running
# Tailscale, MagicDNS resolves the Pi to a private address and the browser
# refuses a public page access to the local address space, killing the video and
# the vitals together.
DEFAULT_STREAM_URL = "/owl/index.m3u8"
DEFAULT_DIAGNOSTICS_URL = "/diagnostics"
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


def _head(*, title: str, description: str, include_player: bool) -> Head:
    scripts = [Script(src="/assets/admin.js", defer=True)]
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
    moments = {"aria_current": "page"} if active == "moments" else {}
    about = {"aria_current": "page"} if active == "about" else {}
    return Div(
        A("CARVER FIELD STATION", href="/", cls="eyebrow", **home),
        Nav(
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
                    value="admin",
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
                    H2("Camera feed"),
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
                aria_label="Live video control",
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
                    "Analytics is not configured. This verifies that Firebase "
                    "is reachable and still redirects to the Pi."
                ),
                cls="admin-section",
            ),
            Section(
                Div(
                    H2("Service logs"),
                    Div(
                        Label("Unit", fr="admin-log-service"),
                        Select(
                            Option("Stream", value="stream"),
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


def render_page(stream_url: str = DEFAULT_STREAM_URL) -> str:
    page = Html(
        _head(
            title="Carver OwlCam — Live from the Nest",
            description="A private live look inside the Carver owl nest.",
            include_player=True,
        ),
        Body(
            _nav(active="live"),
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
                            Small("1920 × 1080 · H.264 · Carver OwlCam"),
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
            Script(src="/assets/moments.js", defer=True),
        ),
        lang="en",
    )
    return to_xml(page)
