from pathlib import Path
from shutil import copytree, rmtree

from app import render_page

WEB_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = WEB_ROOT / "public"


def build_site(output: Path = DEFAULT_OUTPUT) -> None:
    if output.exists():
        rmtree(output)
    output.mkdir(parents=True)
    (output / "index.html").write_text(render_page(), encoding="utf-8")
    copytree(WEB_ROOT / "static", output / "assets")


if __name__ == "__main__":
    build_site()
    print(f"Built Firebase site at {DEFAULT_OUTPUT}")
