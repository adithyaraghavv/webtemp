"""Adds the QR table-ordering pages to a site folder. Standard library only.
The browser pages go into <site>/order/ (public). The SQL goes OUTSIDE the site folder so it is never published."""
from __future__ import annotations

import base64
import json
import re
import shutil
from importlib import resources
from pathlib import Path

URL_OK = re.compile(r"^(https://[a-z0-9-]+\.supabase\.co|http://(localhost|127\.0\.0\.1)(:\d{2,5})?)$")


def check_public_key(key: str) -> None:
    """Refuse anything that looks like a secret key: only the publishable (anon) key may go into a web page."""
    if not key:
        return
    if key.startswith("sb_secret_"):
        raise ValueError("that is a secret key; only the publishable key (sb_publishable_... or the anon key) may go in a web page")
    parts = key.split(".")
    if len(parts) == 3:
        try:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            role = json.loads(base64.urlsafe_b64decode(pad)).get("role")
        except Exception:
            role = None
        if role and role != "anon":
            raise ValueError(f"this key has role {role!r}; only the anon / publishable key may go in a web page")
    elif not key.startswith("sb_publishable_"):
        raise ValueError("unrecognised key format; use the publishable key (sb_publishable_...) or the anon JWT")


def init(site_dir: str, url: str = "", key: str = "", sql_out: str | None = None) -> dict:
    if url and not URL_OK.match(url):
        raise ValueError("url must look like https://<project>.supabase.co")
    check_public_key(key)
    site = Path(site_dir)
    if not site.is_dir():
        raise FileNotFoundError(f"site folder not found: {site}")
    kit = resources.files("webbuild") / "ordering_kit"
    dest = site / "order"
    dest.mkdir(exist_ok=True)
    copied = []
    for f in (kit / "web").iterdir():
        if f.name == "config.js":
            continue
        (dest / f.name).write_bytes(f.read_bytes())
        copied.append(f.name)
    (dest / "config.js").write_text(
        "/* Public settings for this cafe: Supabase URL and the PUBLISHABLE key only. */\n"
        "window.CAFE = " + json.dumps({"url": url, "key": key}) + ";\n")
    sql = Path(sql_out) if sql_out else site.resolve().parent / "ordering-sql"
    sql.mkdir(parents=True, exist_ok=True)
    for f in sorted((kit / "supabase").iterdir()):
        (sql / f.name).write_bytes(f.read_bytes())
    return {"pages": str(dest), "sql": str(sql), "files": sorted(copied), "configured": bool(url and key)}
