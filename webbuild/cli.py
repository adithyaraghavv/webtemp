from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .assets import command_md
from .frames import extract
from .site import build, validate

EXAMPLE = {
    "name": "Cafe Example", "tagline": "Slow coffee. Fast Wi-Fi.", "lang": "en", "currency": "Rs ",
    "theme": {"bg": "#0e0c0b", "fg": "#f4efe9", "accent": "#d7263d", "heading_font": "Playfair Display", "body_font": "Inter"},
    "hero": {"frames": 120, "dir": "frames/", "ext": ".jpg", "pad": 4, "poster": "poster.jpg"},
    "about_title": "Our story", "about": "Two sentences about the place, in the owner's own words.",
    "menu": [{"category": "Coffee", "items": [{"name": "Filter coffee", "desc": "South Indian style", "price": "90", "image": "img/filter.jpg"}]}],
    "gallery": ["img/1.jpg", "img/2.jpg"],
    "hours": [{"days": "Mon to Sun", "time": "8 am to 11 pm"}],
    "address": "12 Example Road, Bengaluru", "phone": "+919876543210", "whatsapp": "+919876543210",
    "map_url": "https://maps.google.com/?q=Cafe+Example", "cta_label": "Find us", "cta_title": "Your table is waiting",
}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="webbuild", description="Website builder kit")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frames", help="video to scroll-hero frames")
    f.add_argument("video")
    f.add_argument("--out", default="site/frames")
    f.add_argument("--count", type=int, default=120)
    f.add_argument("--width", type=int, default=1280)
    b = sub.add_parser("build", help="brief.json to site/index.html")
    b.add_argument("brief")
    b.add_argument("--out", default="site")
    sub.add_parser("example", help="print an example brief.json")
    c = sub.add_parser("check", help="validate a brief")
    c.add_argument("brief")
    s = sub.add_parser("setup", help="install the /webbuild command for Claude Code")
    s.add_argument("--repo", default="adithyaraghavv/webbuild")
    s.add_argument("--home", help=argparse.SUPPRESS)
    a = p.parse_args(argv)

    try:
        if a.cmd == "example":
            print(json.dumps(EXAMPLE, indent=2))
        elif a.cmd == "check":
            errs = validate(json.loads(Path(a.brief).read_text()))
            print("\n".join(errs) if errs else "brief OK")
            return 1 if errs else 0
        elif a.cmd == "frames":
            print(json.dumps(extract(a.video, a.out, a.count, a.width)))
        elif a.cmd == "build":
            print(f"wrote {build(a.brief, a.out)}")
        elif a.cmd == "setup":
            import re
            if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", a.repo):
                print("setup error: repo must look like owner/name", file=sys.stderr)
                return 2
            dest = (Path(a.home) if a.home else Path.home()) / ".claude" / "commands" / "webbuild.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(command_md(a.repo))
            print(f"installed /webbuild command: {dest}")
    except (OSError, ValueError, RuntimeError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
