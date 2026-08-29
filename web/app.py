from fasthtml.common import (
    A,
    Body,
    Button,
    Div,
    Footer,
    H1,
    H2,
    Head,
    Html,
    Link,
    Main,
    Meta,
    P,
    Script,
    Section,
    Small,
    Span,
    Title,
    Video,
    to_xml,
)

DEFAULT_STREAM_URL = (
    "https://owlcam.tail31318f.ts.net/owl/index.m3u8"
)


def render_page(stream_url: str = DEFAULT_STREAM_URL) -> str:
    page = Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(
                name="description",
                content="A private live look inside the Carver owl nest.",
            ),
            Title("Carver OwlCam — Live from the Nest"),
            Link(rel="preconnect", href="https://cdn.jsdelivr.net"),
            Link(rel="stylesheet", href="/assets/styles.css"),
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
        ),
        Body(
            Div(
                Span("CARVER FIELD STATION", cls="eyebrow"),
                Span("PRIVATE TAILNET FEED", cls="access-pill"),
                cls="utility-bar",
            ),
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
                                muted=True,
                                playsinline=True,
                                preload="metadata",
                                aria_label="Carver OwlCam livestream",
                                data_stream_url=stream_url,
                            ),
                            Div(
                                Div("◉", cls="owl-mark", aria_hidden="true"),
                                H2("Camera is resting"),
                                P(
                                    "The feed reconnects automatically when "
                                    "OwlCam is online and your device is on "
                                    "the authorized Tailscale network."
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
                                    "Checking private feed…",
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
                        H2("Private by design"),
                        P(
                            "Video stays on Tailscale. The public demo shell "
                            "never exposes camera ports."
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
            Footer(
                P(
                    "CARVER OWLCAM",
                    Span(" · ", aria_hidden="true"),
                    A(
                        "View the project",
                        href="https://github.com/ssskillman/owlcam",
                    ),
                ),
                P("Observe quietly. Protect the habitat."),
            ),
        ),
        lang="en",
    )
    return to_xml(page)
