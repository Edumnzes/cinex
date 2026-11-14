"""WCAG contrast helpers used by `project.py contraste` and qa.py (no outline/glow: contrast must be measured)."""
import sys, unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import reels_lib as R


class ContrastTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(float(R.contrast_ratio((0, 0, 0), (255, 255, 255))), 21.0, places=1)
        self.assertAlmostEqual(float(R.contrast_ratio((255, 255, 255), (255, 255, 255))), 1.0, places=3)
        self.assertAlmostEqual(float(R.contrast_ratio((118, 118, 118), (255, 255, 255))), 4.54, places=1)   # WCAG grey limit

    def test_arrays_and_symmetry(self):
        bg = np.array([[0, 0, 0], [200, 200, 200]])
        r = R.contrast_ratio((255, 205, 40), bg)
        self.assertEqual(r.shape, (2,)); self.assertGreater(r[0], 10); self.assertLess(r[1], 2)
        self.assertAlmostEqual(float(R.contrast_ratio((10, 20, 30), (200, 100, 50))), float(R.contrast_ratio((200, 100, 50), (10, 20, 30))))

    def test_thresholds_from_rules(self):
        thr, big = R.contrast_thresholds()
        self.assertEqual((thr, big), (4.5, 3.0))


if __name__ == "__main__":
    unittest.main()
