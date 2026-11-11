from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .assets import command_md
from .frames import extract
from .lint import lint_dir, report
from . import ordering
from .theme import theme_from_photos
from .site import PRESETS, advice, build, validate

EXAMPLE = {
    "name": "Cafe Example", "direction": "warm and editorial: paper tones, serif headlines, real photos, one accent",
    "register": "brand", "tagline": "Slow coffee. Fast Wi-Fi.", "lang": "en", "currency": "Rs ",
    "theme": {"preset": "paper"},
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
    ln = sub.add_parser("lint", help="design and quality checks on a built site folder")
    ln.add_argument("site", nargs="?", default="site")
    sub.add_parser("presets", help="list design presets")
    c = sub.add_parser("check", help="validate a brief")
    c.add_argument("brief")
    o = sub.add_parser("ordering", help="add QR table ordering pages to a built site")
    osub = o.add_subparsers(dest="ocmd", required=True)
    oi = osub.add_parser("init", help="copy the ordering pages into SITE/order and the SQL next to the site (not inside it)")
    oi.add_argument("site", nargs="?", default="site")
    oi.add_argument("--url", default="", help="https://<project>.supabase.co")
    oi.add_argument("--key", default="", help="publishable (anon) key only")
    oi.add_argument("--sql-out", default=None, help="where to put the SQL (default: ../ordering-sql)")
    th = sub.add_parser("theme", help="suggest colours and fonts from the cafe's photos (prints a theme block for brief.json)")
    th.add_argument("photos", nargs="+")
    s = sub.add_parser("setup", help="install the /webbuild command for Claude Code")
    s.add_argument("--repo", default="adithyaraghavv/webtemp")
    s.add_argument("--home", help=argparse.SUPPRESS)
    a = p.parse_args(argv)

    try:
        if a.cmd == "example":
            print(json.dumps(EXAMPLE, indent=2))
        elif a.cmd == "presets":
            print("\n".join(PRESETS))
        elif a.cmd == "lint":
            issues = lint_dir(a.site)
            print(report(issues))
            return 1 if any(i.grade == "FAIL" for i in issues) else 0
        elif a.cmd == "check":
            brief = json.loads(Path(a.brief).read_text())
            errs = validate(brief)
            print("\n".join(errs) if errs else "brief OK")
            for n in advice(brief):
                print("note: " + n)
            return 1 if errs else 0
        elif a.cmd == "ordering":
            r = ordering.init(a.site, a.url, a.key, a.sql_out)
            print(json.dumps(r, indent=2))
            if not r["configured"]:
                print("note: no url/key given; fill in order/config.js before use. Run the SQL files in order on the cafe's own Supabase project.")
        elif a.cmd == "theme":
            print(json.dumps({"theme": theme_from_photos(a.photos)}, indent=2))
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
