from hashlib import sha256
from pathlib import Path
from shutil import copytree, rmtree

from app import render_about_page, render_moments_page, render_page

WEB_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = WEB_ROOT / "public"

# CSS and JS change with every deploy, so their URLs carry a content hash.
# Without it a browser keeps a cached stylesheet and renders the new markup
# unstyled until the old TTL expires.
FINGERPRINTED = ("styles.css", "player.js", "moments.js")
PAGES = {
    "index.html": render_page,
    "about.html": render_about_page,
    "moments.html": render_moments_page,
}


def _fingerprint(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()[:12]


def build_site(output: Path = DEFAULT_OUTPUT) -> None:
    if output.exists():
        rmtree(output)
    output.mkdir(parents=True)
    for name, render in PAGES.items():
        (output / name).write_text(render(), encoding="utf-8")

    assets = output / "assets"
    copytree(WEB_ROOT / "static", assets)

    renamed: dict[str, str] = {}
    for name in FINGERPRINTED:
        source = assets / name
        stem, extension = name.rsplit(".", 1)
        hashed = f"{stem}.{_fingerprint(source)}.{extension}"
        source.rename(assets / hashed)
        renamed[name] = hashed

    for name in PAGES:
        page = output / name
        markup = page.read_text(encoding="utf-8")
        for original, hashed in renamed.items():
            markup = markup.replace(f"/assets/{original}", f"/assets/{hashed}")
        page.write_text(markup, encoding="utf-8")


if __name__ == "__main__":
    build_site()
    print(f"Built Firebase site at {DEFAULT_OUTPUT}")
