import json, re, subprocess, tempfile, unittest
from pathlib import Path
from webbuild.cli import EXAMPLE, main
from webbuild.frames import extract
from webbuild.site import advice, render, validate
from webbuild.lint import lint_html


class SiteTests(unittest.TestCase):
    def test_example_renders(self):
        h = render(EXAMPLE)
        self.assertIn("<canvas", h)
        self.assertIn("Filter coffee", h)
        self.assertIn("wa.me/919876543210", h)

    def test_escapes_html(self):
        b = {**EXAMPLE, "name": "<script>alert(1)</script>", "about": "<img src=x onerror=1>"}
        h = render(b)
        self.assertNotIn("<script>alert(1)", h)
        self.assertNotIn("<img src=x", h)

    def test_validation(self):
        self.assertTrue(validate({}))
        self.assertTrue(validate({"name": "x", "theme": {"bg": "red;}</style>"}}))
        self.assertTrue(validate({"name": "x", "phone": "abc"}))
        self.assertTrue(validate({"name": "x", "theme": {"body_font": "a');}"}}))
        with self.assertRaises(ValueError):
            render({"name": "x", "theme": {"accent": "javascript:1"}})

    def test_no_video_still_works(self):
        h = render({"name": "Plain"})
        self.assertIn("Plain", h)

    def test_cli_build_and_setup(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.json"
            b.write_text(json.dumps(EXAMPLE))
            self.assertEqual(main(["build", str(b), "--out", str(Path(d) / "s")]), 0)
            self.assertTrue((Path(d) / "s" / "index.html").exists())
            self.assertEqual(main(["setup", "--home", d]), 0)
            self.assertIn("webbuild frames", (Path(d) / ".claude/commands/webbuild.md").read_text())
            self.assertEqual(main(["setup", "--home", d, "--repo", "bad repo"]), 2)
            self.assertEqual(main(["build", str(Path(d) / "nope.json")]), 2)


class FrameCountTests(unittest.TestCase):
    def test_build_uses_real_frame_count(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "site"
            (out / "frames").mkdir(parents=True)
            for i in range(1, 8):
                (out / "frames" / f"{i:04d}.jpg").write_bytes(b"x")
            b = Path(d) / "b.json"
            b.write_text(json.dumps({**EXAMPLE, "hero": {"frames": 120}}))
            self.assertEqual(main(["build", str(b), "--out", str(out)]), 0)
            self.assertIn("var n=7,", (out / "index.html").read_text())

    def test_no_frames_dir_means_no_animation(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.json"
            b.write_text(json.dumps({**EXAMPLE, "hero": {"frames": 120}}))
            main(["build", str(b), "--out", str(Path(d) / "s")])
            self.assertIn("var n=0,", (Path(d) / "s" / "index.html").read_text())


class LintTests(unittest.TestCase):
    def test_every_preset_passes_its_own_linter(self):
        from webbuild.lint import lint_html
        from webbuild.site import PRESETS
        for name in PRESETS:
            fails = [i for i in lint_html(render({**EXAMPLE, "theme": {"preset": name}})) if i.grade == "FAIL"]
            self.assertEqual(fails, [], name)

    def test_linter_catches_common_tells(self):
        from webbuild.lint import lint_html
        bad = """<html><head><title>x</title><style>body{color:#fff;background:#000;font-family:Inter}
        .a{transition:all .3s;background:linear-gradient(#7c3aed,#2563eb)}</style></head>
        <body><h1>Elevate your experience</h1><p>seamless \U0001F680</p><img src=a.jpg><canvas></canvas></body></html>"""
        rules = {i.rule for i in lint_html(bad)}
        for r in ("html-lang", "viewport", "img-alt", "canvas-a11y", "tokens-color", "tokens-font", "pure-bw",
                  "transition-all", "focus", "overflow-x", "purple-blue", "filler-copy", "emoji"):
            self.assertIn(r, rules, r)

    def test_contrast_failure_detected(self):
        from webbuild.lint import lint_html
        h = render({**EXAMPLE, "theme": {"preset": "paper", "muted": "#cfc6b6"}})
        self.assertIn("contrast", {i.rule for i in lint_html(h)})

    def test_bad_preset_rejected(self):
        self.assertTrue(validate({"name": "x", "theme": {"preset": "nope"}}))

    def test_cli_lint(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.json"
            b.write_text(json.dumps(EXAMPLE))
            main(["build", str(b), "--out", str(Path(d) / "s")])
            (Path(d) / "s" / "img").mkdir()
            for f in ("img/filter.jpg", "img/1.jpg", "img/2.jpg", "poster.jpg"):
                (Path(d) / "s" / f).write_bytes(b"x")
            (Path(d) / "s" / "frames").mkdir()
            self.assertEqual(main(["lint", str(Path(d) / "s")]), 0)
            (Path(d) / "s" / "index.html").write_text("<html></html>")
            self.assertEqual(main(["lint", str(Path(d) / "s")]), 1)


class MissingFileTests(unittest.TestCase):
    def test_missing_images_and_frames_fail(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.json"
            b.write_text(json.dumps(EXAMPLE))
            main(["build", str(b), "--out", str(Path(d) / "s")])
            from webbuild.lint import lint_dir
            rules = {i.rule for i in lint_dir(str(Path(d) / "s"))}
            self.assertIn("missing-file", rules)  # img/filter.jpg etc. are not there
            (Path(d) / "s" / "frames").mkdir()
            for i in range(1, 4):
                (Path(d) / "s" / "frames" / f"{i:04d}.jpg").write_bytes(b"x")
            html = (Path(d) / "s" / "index.html").read_text().replace("var n=0,", "var n=9,")
            (Path(d) / "s" / "index.html").write_text(html)
            self.assertIn("missing-frames", {i.rule for i in lint_dir(str(Path(d) / "s"))})


class AiTellTests(unittest.TestCase):
    def rules(self, extra_css="", body="", root=""):
        base = EXAMPLE
        page = render(base)
        page = page.replace("</style>", extra_css + "</style>", 1).replace("</body>", body + "</body>", 1)
        if root:
            page = page.replace(":root{", ":root{" + root, 1)
        return {i.rule for i in lint_html(page)}

    def test_bounce_and_glass(self):
        r = self.rules(".a{transition:transform .3s cubic-bezier(.34,1.56,.64,1)}"
                       ".b{backdrop-filter:blur(8px)}.c{backdrop-filter:blur(4px)}")
        self.assertIn("bounce-easing", r)
        self.assertIn("glass", r)

    def test_overused_and_same_font(self):
        page = render(EXAMPLE).replace("--font-head:'", "--font-head:'Inter', '", 1)
        self.assertIn("overused-font", {i.rule for i in lint_html(page)})
        page = render(EXAMPLE)
        page = re.sub(r"--font-body:'[^']*'", "--font-body:'Fraunces'", page)
        page = re.sub(r"--font-head:'[^']*'", "--font-head:'Fraunces'", page)
        self.assertIn("no-pairing", {i.rule for i in lint_html(page)})

    def test_cards(self):
        cards = '<div class="card">a</div>' * 3
        self.assertIn("card-grid", self.rules(body=cards))
        self.assertIn("nested-cards", self.rules(body='<div class="card"><div class="card">x</div></div>'))
        priced = '<div class="card"><span class="price">1</span></div>' * 4
        self.assertNotIn("card-grid", self.rules(body=priced))

    def test_sparkline_and_grey(self):
        self.assertIn("sparkline", self.rules(body='<svg class="sparkline"></svg>'))
        page = render(EXAMPLE)
        page = re.sub(r"--card:#[0-9a-fA-F]{6}", "--card:#808080", page, count=1)
        self.assertIn("untinted-neutral", {i.rule for i in lint_html(page)})

    def test_direction_advice(self):
        self.assertTrue(advice({"name": "x"}))
        self.assertFalse(advice({"name": "x", "direction": "dark and cinematic"}))
        self.assertTrue(advice({"name": "x", "direction": "a", "register": "weird"}))


class RestaurantTests(unittest.TestCase):
    B = {**EXAMPLE, "template": "restaurant", "theme": {"preset": "cantina"}, "order_url": "https://example.com/o",
         "phone": "+919876543210", "visit_image": "img/v.jpg", "cta_label": "Order now"}

    def test_renders_sections_and_passes_lint(self):
        h = render(self.B)
        for needle in ('class="rest"', 'data-fx="1"', 'class="ready"', 'class="mcat', 'class="find has-photo"',
                       "Order now", "Explore the menu"):
            self.assertIn(needle, h)
        self.assertNotIn('class="card"', h)  # no identical card grid
        self.assertEqual([i for i in lint_html(h) if i.grade == "FAIL"], [])

    def test_reveal_defaults_visible_without_js_or_frames(self):
        h = render({**self.B, "hero": {"poster": "poster.jpg"}})
        self.assertIn("opacity:var(--reveal,1)", h)
        self.assertIn("var n=0,", h)

    def test_no_guessed_directions(self):
        self.assertNotIn("Get directions", render({k: v for k, v in self.B.items() if k != "map_url"}))
        self.assertIn("Get directions", render({**self.B, "map_url": "https://maps.example/x"}))

    def test_escape_and_bad_template(self):
        h = render({**self.B, "name": "<script>x</script>"})
        self.assertNotIn("<script>x</script>", h)
        self.assertTrue(validate({"name": "x", "template": "nope"}))

    def test_preset_cantina_listed(self):
        from webbuild.site import PRESETS
        self.assertIn("cantina", PRESETS)


class OrderingInitTests(unittest.TestCase):
    def test_copies_pages_and_keeps_sql_out_of_the_site(self):
        from webbuild import ordering
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            r = ordering.init(str(site), "https://abc.supabase.co", "sb_publishable_abc123")
            for f in ("order.html", "staff.html", "tables.html", "api.js", "qr.js", "ui.css", "config.js"):
                self.assertTrue((site / "order" / f).exists(), f)
            self.assertTrue(r["configured"])
            self.assertEqual(sorted(x.name for x in (Path(d) / "ordering-sql").iterdir()), ["001_schema.sql", "002_bill_rating_staff.sql"])
            self.assertFalse(list(site.rglob("*.sql")))  # never published
            cfg = (site / "order" / "config.js").read_text()
            self.assertIn("https://abc.supabase.co", cfg)

    def test_refuses_secret_keys_and_bad_urls(self):
        import base64, json as j
        from webbuild import ordering
        jwt = lambda role: "h." + base64.urlsafe_b64encode(j.dumps({"role": role}).encode()).decode().rstrip("=") + ".s"
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            for bad in ("sb_secret_xyz", jwt("service_role"), "random-string"):
                with self.assertRaises(ValueError):
                    ordering.init(str(site), "https://abc.supabase.co", bad)
            with self.assertRaises(ValueError):
                ordering.init(str(site), "https://evil.example.com", "sb_publishable_x")
            ordering.init(str(site), "https://abc.supabase.co", jwt("anon"))  # anon JWT is fine
            with self.assertRaises(FileNotFoundError):
                ordering.init(str(Path(d) / "nope"))

    def test_cli_and_quote_safety(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            self.assertEqual(main(["ordering", "init", str(site)]), 0)
            self.assertIn('"url": ""', (site / "order" / "config.js").read_text())
            self.assertEqual(main(["ordering", "init", str(site), "--url", "http://evil.test", "--key", "k"]), 2)


class FramesTests(unittest.TestCase):
    def test_extract(self):
        with tempfile.TemporaryDirectory() as d:
            v = str(Path(d) / "v.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=25",
                            "-pix_fmt", "yuv420p", v], check=True)
            r = extract(v, str(Path(d) / "f"), count=30, width=160)
            self.assertEqual(r["frames"], 30)
            self.assertEqual(len(list((Path(d) / "f").glob("*.jpg"))), 30)
            with self.assertRaises(ValueError):
                extract(v, str(Path(d) / "g"), count=1)
            with self.assertRaises(FileNotFoundError):
                extract(str(Path(d) / "none.mp4"), str(Path(d) / "h"))


if __name__ == "__main__":
    unittest.main()
