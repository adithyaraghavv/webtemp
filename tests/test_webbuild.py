import json, subprocess, tempfile, unittest
from pathlib import Path
from webbuild.cli import EXAMPLE, main
from webbuild.frames import extract
from webbuild.site import render, validate


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
