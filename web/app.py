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
    Img,
    Link,
    Main,
    Meta,
    Nav,
    P,
    Script,
    Section,
    Small,
    Span,
    Title,
    Video,
    to_xml,
)

DEFAULT_STREAM_URL = "https://owlcam.tail31318f.ts.net/owl/index.m3u8"
AMG_TEAM_URL = "https://www.aquaticmanagementgroup.com/the-executive-team"
MOMENTS = (
    {
        "filename": "barred-owl-portrait.jpg",
        "timestamp": "2006-12-26",
        "type": "photo",
        "subject": "Adult portrait",
        "alt": "Barred owl perched among bare branches",
        "story": (
            "A quiet adult holds the edge of the woods, listening before "
            "the next flight. On OwlCam, a pause like this could be a parent "
            "checking that the path home is clear."
        ),
        "credit": "D. Gordon E. Robertson · CC BY-SA 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Barred_owl.jpg",
        "license": "https://creativecommons.org/licenses/by-sa/3.0",
    },
    {
        "filename": "florida-perch.jpg",
        "timestamp": "2011-01-24",
        "type": "photo",
        "subject": "Branch watch",
        "alt": "Barred owl looking down from a tree branch",
        "story": (
            "The round face works like a satellite dish, gathering tiny "
            "sounds below. A resident parent might use this patient lookout "
            "to choose the safest moment to return to the chicks."
        ),
        "credit": "DickDaniels · CC BY-SA 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Barred_Owl_RWD2.jpg",
        "license": "https://creativecommons.org/licenses/by-sa/3.0",
    },
    {
        "filename": "mother-at-dusk.jpg",
        "timestamp": "2018-07-28",
        "type": "photo",
        "subject": "Mother at dusk",
        "alt": "Female barred owl perched shortly after sunset",
        "story": (
            "Dusk belongs to this mother. The source notes that she raised "
            "four chicks that year; this watchful stop may have come between "
            "the evening's many trips through the trees."
        ),
        "credit": "Sixflashphoto · CC BY-SA 4.0",
        "source": (
            "https://commons.wikimedia.org/wiki/"
            "File:Innis_Woods_-_Barred_Owl_2.jpg"
        ),
        "license": "https://creativecommons.org/licenses/by-sa/4.0",
    },
    {
        "filename": "winter-watch.jpg",
        "timestamp": "2005-01-01",
        "type": "photo",
        "subject": "Winter watch",
        "alt": "Barred owl perched in winter woodland",
        "story": (
            "Feathers puff into a warm coat while the owl waits out a cold "
            "January morning. If chicks were in the box, both parents would "
            "balance warmth, rest, and the next search for food."
        ),
        "credit": "Mdf · CC BY-SA 3.0",
        "source": "https://commons.wikimedia.org/wiki/File:Strix-varia-005.jpg",
        "license": "https://creativecommons.org/licenses/by-sa/3.0",
    },
    {
        "filename": "cypress-swamp.jpg",
        "timestamp": "2013-04-23",
        "type": "photo",
        "subject": "Nesting season",
        "alt": "Barred owl in a cypress swamp during nesting season",
        "story": (
            "A barred owl settles into the layered greens of a cypress "
            "swamp. During nesting season, stillness can hide a busy family "
            "rhythm: guard, hunt, feed, repeat."
        ),
        "credit": 'Gregory "Slobirdr" Smith · CC BY-SA 2.0',
        "source": (
            "https://commons.wikimedia.org/wiki/"
            "File:Barred_Owl_(Strix_varia)_(9732594639).jpg"
        ),
        "license": "https://creativecommons.org/licenses/by-sa/2.0",
    },
    {
        "filename": "mole-delivery.webm",
        "timestamp": "2013-07-21",
        "type": "video",
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


def _head(*, title: str, description: str, include_player: bool) -> Head:
    scripts = []
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
        ]
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=description),
        Title(title),
        Link(rel="preconnect", href="https://cdn.jsdelivr.net"),
        Link(rel="stylesheet", href="/assets/styles.css"),
        *scripts,
    )


def _nav(*, active: str) -> Div:
    live = {"aria_current": "page"} if active == "live" else {}
    moments = {"aria_current": "page"} if active == "moments" else {}
    about = {"aria_current": "page"} if active == "about" else {}
    return Div(
        Span("CARVER FIELD STATION", cls="eyebrow"),
        Nav(
            A("Live", href="/", **live),
            A("Moments", href="/moments", **moments),
            A("About", href="/about", **about),
            cls="site-nav",
            aria_label="Site",
        ),
        cls="utility-bar",
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
            Main(
                Section(
                    Span("ABOUT", cls="live-label"),
                    H1("Chris Carver.", Span("Good dude.", cls="accent")),
                    P(
                        "This nest camera exists so friends, family, and "
                        "anyone who will linger a minute can share a quiet "
                        "look at the woods with Chris. Enjoy his love of "
                        "nature. Share the OwlCam moments with him.",
                        cls="lede",
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
                        P(
                            A(
                                "AMG executive team",
                                href=AMG_TEAM_URL,
                                rel="noopener noreferrer",
                            ),
                            " · Chris Carver, Chief Service Officer and owner"
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


def _moment_card(item: dict[str, str]) -> Div:
    media = (
        Video(
            src=f"/assets/moments/{item['filename']}",
            controls=True,
            muted=True,
            playsinline=True,
            preload="metadata",
            aria_label=item["alt"],
        )
        if item["type"] == "video"
        else Img(
            src=f"/assets/moments/{item['filename']}",
            alt=item["alt"],
            loading="lazy",
        )
    )
    return Div(
        Div(
            media,
            Span("PLACEHOLDER", cls="placeholder-badge"),
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
                Span("AI-GENERATED PLACEHOLDER STORY", cls="story-label"),
                " · ",
                item["filename"],
                cls="moment-file",
            ),
            P(
                "Media: ",
                A(
                    item["credit"],
                    href=item["source"],
                    rel="noopener noreferrer",
                ),
                " · ",
                A(
                    "license",
                    href=item["license"],
                    rel="noopener noreferrer",
                ),
                cls="moment-credit",
            ),
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
                "A sortable field log for OwlCam action shots, short clips, "
                "and AI-generated stories about the barred owl family."
            ),
            include_player=False,
        ),
        Body(
            _nav(active="moments"),
            Main(
                Section(
                    Span("FIELD LOG / PREVIEW", cls="live-label"),
                    H1("Small moments.", Span("Wild stories.", cls="accent")),
                    P(
                        "A future home for OwlCam action shots and short "
                        "clips—with an AI-assisted field note about parents, "
                        "food deliveries, chicks, and movement in the box.",
                        cls="lede",
                    ),
                    P(
                        "These are not OwlCam captures. Every item below is "
                        "a licensed barred-owl placeholder, and each story is "
                        "a clearly labeled sample—not a factual observation "
                        "from the Carver nest.",
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
