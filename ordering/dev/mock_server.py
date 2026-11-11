"""Local test server: serves ../web and answers the small subset of the Supabase REST API the pages use,
by running the real SQL against a throwaway local Postgres. Development only; never exposed, never Supabase.
Usage: QR_PSQL="runuser -u postgres -- psql -d qrtest" python3 mock_server.py 8780"""
import json, os, re, secrets, shlex, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

WEB = Path(__file__).resolve().parents[2] / "webbuild" / "ordering_kit" / "web"
ROOT = Path(os.environ["QR_SITE"]).resolve() if os.environ.get("QR_SITE") else WEB
STORE = Path(os.environ.get("QR_STORAGE", Path(__file__).resolve().parent / ".storage"))
IMG_TYPES = {"image/jpeg", "image/png", "image/webp"}
FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
PSQL = shlex.split(os.environ["QR_PSQL"])
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
TOKENS = {"staff-token": ("authenticated", "11111111-1111-1111-1111-111111111111"),
          "other-token": ("authenticated", "22222222-2222-2222-2222-222222222222")}
USERS = {("staff@test.cafe", "test-pass"): "staff-token", ("other@test.cafe", "test-pass"): "other-token"}
TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json"}


def lit(v):
    if v is None:
        return "null"
    tag = "q" + secrets.token_hex(4)
    s = v if isinstance(v, str) else json.dumps(v)
    assert f"${tag}$" not in s
    cast = "::jsonb" if isinstance(v, (list, dict)) else ""
    return f"${tag}${s}${tag}${cast}"


def sql_run(role, sub, query):
    script = (f"begin;\nset local role {role};\n"
              f"select set_config('request.jwt.claim.sub', {lit(sub or '')}, true) \\g /dev/null\n{query};\ncommit;\n")
    p = subprocess.run(PSQL + ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"], input=script, capture_output=True, text=True)
    if p.returncode:
        msg = [l for l in p.stderr.splitlines() if "ERROR" in l]
        return False, (msg[-1].split("ERROR:")[-1].strip() if msg else p.stderr.strip()[-200:])
    return True, p.stdout.strip()


def where(qs, skip=("select", "order", "limit")):
    conds = []
    for k, vs in qs.items():
        if k in skip:
            continue
        assert IDENT.match(k)
        op, _, val = vs[0].partition(".")
        if op == "eq":
            conds.append(f"{k} = {lit(val)}")
        elif op == "in":
            items = [x for x in val.strip("()").split(",") if x != ""]
            conds.append(f"{k} in ({','.join(lit(x) for x in items)})")
        else:
            raise ValueError("filter not supported")
    return " where " + " and ".join(conds) if conds else ""


def status_for(msg):
    if "permission denied" in msg or "row-level security" in msg or "not allowed" in msg:
        return 403
    if "violates foreign key" in msg or "duplicate key" in msg:
        return 409
    return 400


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body=b"", ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def who(self):
        a = self.headers.get("Authorization", "")
        return TOKENS.get(a.replace("Bearer ", ""), ("anon", ""))

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def raw(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            return None
        return self.rfile.read(n)

    def is_staff(self):
        role, sub = self.who()
        if role != "authenticated":
            return False
        ok, out = sql_run(role, sub, "select public.is_staff()")
        return ok and out.strip() == "t"

    def do_GET(self):
        u = urlparse(self.path)
        m = re.match(r"^/storage/v1/object/public/menu/([^/]+)$", u.path)
        if m:
            f = STORE / m.group(1)
            if FILE.match(m.group(1)) and f.is_file():
                return self.reply(200, f.read_bytes(), {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(f.suffix.lower(), "application/octet-stream"))
            return self.reply(404, {"message": "not found"})
        if u.path.startswith("/rest/v1/"):
            t = u.path.split("/")[-1]; qs = parse_qs(unquote(u.query))
            try:
                assert IDENT.match(t)
                sel = qs.get("select", ["*"])[0]; sel = sel if re.match(r"^[a-z_,*]+$", sel) else "*"
                order = ""
                if "order" in qs:
                    parts = []
                    for p in qs["order"][0].split(","):
                        c, _, d = p.partition("."); assert IDENT.match(c) and d in ("", "asc", "desc"); parts.append(f"{c} {d or 'asc'}")
                    order = " order by " + ", ".join(parts)
                role, sub = self.who()
                ok, out = sql_run(role, sub, f"select coalesce(json_agg(t), '[]') from (select {sel} from public.{t}{where(qs)}{order}) t")
            except Exception as e:
                return self.reply(400, {"message": str(e)})
            return self.reply(200, out.encode()) if ok else self.reply(status_for(out), {"message": out})
        path = ROOT / (u.path.lstrip("/") or "index.html")
        if path.is_file() and ROOT in path.resolve().parents:
            return self.reply(200, path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"))
        self.reply(404, {"message": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/auth/v1/token":
            b = self.body(); t = USERS.get((b.get("email"), b.get("password")))
            return self.reply(200, {"access_token": t}) if t else self.reply(400, {"error_description": "Invalid login credentials"})
        sm = re.match(r"^/storage/v1/object/menu/([^/]+)$", u.path)
        if sm:
            name = sm.group(1); ctype = self.headers.get("Content-Type", "")
            if not self.is_staff():
                return self.reply(403, {"message": "not allowed"})
            data = self.raw(2 * 1024 * 1024)
            if data is None or not FILE.match(name) or ctype not in IMG_TYPES:
                return self.reply(400, {"message": "file must be a jpeg, png or webp under 2 MB"})
            if (STORE / name).exists() and self.headers.get("x-upsert") != "true":
                return self.reply(409, {"message": "duplicate key: already exists"})
            STORE.mkdir(parents=True, exist_ok=True); (STORE / name).write_bytes(data)
            return self.reply(200, {"Key": "menu/" + name})
        tm = re.match(r"^/rest/v1/([a-z_]+)$", u.path)
        if tm and tm.group(1) != "rpc":
            try:
                t = tm.group(1); rows = self.body(); rows = rows if isinstance(rows, list) else [rows]
                assert rows and all(isinstance(r, dict) for r in rows)
                cols = list(rows[0].keys()); assert all(IDENT.match(c) for c in cols) and all(list(r.keys()) == cols for r in rows)
                vals = ", ".join("(" + ", ".join(lit(r[c]) for c in cols) + ")" for r in rows)
                role, sub = self.who()
                q = f"with ins as (insert into public.{t} ({', '.join(cols)}) values {vals} returning *) select coalesce(json_agg(ins), '[]') from ins"
                ok, out = sql_run(role, sub, q)
            except Exception as e:
                return self.reply(400, {"message": str(e)})
            if not ok:
                return self.reply(status_for(out), {"message": out})
            return self.reply(201, out.encode()) if "return=representation" in self.headers.get("Prefer", "") else self.reply(201)
        m = re.match(r"^/rest/v1/rpc/([a-z_]+)$", u.path)
        if not m:
            return self.reply(404, {"message": "not found"})
        args = self.body(); role, sub = self.who()
        call = ", ".join(f"{k} => {lit(v)}" for k, v in args.items() if IDENT.match(k))
        ok, out = sql_run(role, sub, f"select to_json(public.{m.group(1)}({call}))")
        if ok:
            return self.reply(200, (out or "null").encode())
        self.reply(status_for(out), {"message": out})

    def do_PATCH(self):
        u = urlparse(self.path); t = u.path.split("/")[-1]; qs = parse_qs(unquote(u.query))
        try:
            assert IDENT.match(t); b = self.body()
            sets = ", ".join(f"{k} = {lit(v)}" for k, v in b.items() if IDENT.match(k))
            role, sub = self.who()
            ok, out = sql_run(role, sub, f"update public.{t} set {sets}{where(qs)}")
        except Exception as e:
            return self.reply(400, {"message": str(e)})
        self.reply(204) if ok else self.reply(status_for(out), {"message": out})

    def do_DELETE(self):
        u = urlparse(self.path); qs = parse_qs(unquote(u.query))
        m = re.match(r"^/storage/v1/object/menu/([^/]+)$", u.path)
        if m:
            if not self.is_staff() or not FILE.match(m.group(1)):
                return self.reply(403, {"message": "not allowed"})
            (STORE / m.group(1)).unlink(missing_ok=True)
            return self.reply(200, {"message": "removed"})
        try:
            t = u.path.split("/")[-1]; assert IDENT.match(t) and qs, "a filter is required"
            role, sub = self.who()
            ok, out = sql_run(role, sub, f"delete from public.{t}{where(qs)}")
        except Exception as e:
            return self.reply(400, {"message": str(e)})
        self.reply(204) if ok else self.reply(status_for(out), {"message": out})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8780), H).serve_forever()
