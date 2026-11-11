"""Checks our own QR encoder by decoding what it draws with OpenCV (skipped if node or cv2 is missing)."""
import json, random, shutil, subprocess, unittest
from pathlib import Path

QR_JS = Path(__file__).resolve().parents[2] / "webbuild" / "ordering_kit" / "web" / "qr.js"
try:
    import cv2, numpy as np
except Exception:
    cv2 = None


@unittest.skipUnless(shutil.which("node") and cv2, "needs node and opencv")
class QrEncoder(unittest.TestCase):
    def test_random_strings_all_versions_decode(self):
        rnd = random.Random(7)
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/?&=@._-% "
        samples = ["hello", "upi://pay?pa=test.cafe@upi&pn=Brew%20House&am=320.00&cu=INR&tn=Bill%20ab12cd34"] + [
            "".join(rnd.choice(chars) for _ in range(rnd.randint(1, 200))) for _ in range(60)]
        js = ("const QR=require(%s);const s=JSON.parse(process.argv[1]);"
              "console.log(JSON.stringify(s.map(x=>QR.matrix(x))))") % json.dumps(str(QR_JS))
        mats = json.loads(subprocess.run(["node", "-e", js, json.dumps(samples)], capture_output=True, text=True, check=True).stdout)
        dets = [cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()]
        bad = []
        for s, m in zip(samples, mats):
            m = np.array(m, dtype=np.uint8)
            ok = False
            for det in dets:
                for sc in (6, 8, 10):  # decoders are picky about scale; a valid symbol decodes at some scale
                    img = np.pad(np.kron(1 - m, np.ones((sc, sc), dtype=np.uint8)) * 255, sc * 5, constant_values=255)
                    if det.detectAndDecode(img)[0] == s:
                        ok = True; break
                if ok:
                    break
            if not ok:
                bad.append(s[:30])
        self.assertEqual(bad, [])

    def test_too_long_is_an_error(self):
        r = subprocess.run(["node", "-e", "require(%s).matrix('x'.repeat(400))" % json.dumps(str(QR_JS))], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
