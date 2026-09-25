"""scripts/mushroom_prepare.py: pose conversion, COLMAP text parsing, splits, alignment."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import mushroom_prepare as mp  # noqa: E402


def random_rotation(rng):
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    return mp.qvec_to_rot(q)


class Rotations(unittest.TestCase):
    def test_quaternion_round_trip(self):
        rng = np.random.default_rng(0)
        for _ in range(200):
            R = random_rotation(rng)
            q = mp.rot_to_qvec(R)
            self.assertGreaterEqual(q[0], 0)
            np.testing.assert_allclose(mp.qvec_to_rot(q), R, atol=1e-9)

    def test_opengl_camera_to_colmap(self):
        # OpenGL camera at C looking down world -z (its own -z): identity rotation.
        C = np.array([1.0, 2.0, 3.0])
        c2w = np.eye(4)
        c2w[:3, 3] = C
        q, t = mp.colmap_pose(c2w)
        R = mp.qvec_to_rot(q)
        np.testing.assert_allclose(-R.T @ t, C, atol=1e-12)            # centre preserved
        # a point 1 m in front of the camera (world -z) must have positive OpenCV depth
        p_cam = R @ (C + np.array([0, 0, -1.0])) + t
        np.testing.assert_allclose(p_cam, [0, 0, 1.0], atol=1e-12)
        # OpenGL +y (up) must map to OpenCV -y (image rows grow downward)
        p_up = R @ (C + np.array([0, 1.0, -1.0])) + t
        self.assertLess(p_up[1], 0)


class ImagesTxt(unittest.TestCase):
    def test_blank_points_line_does_not_shift_images(self):
        txt = ("# comment\n"
               "1 1 0 0 0 0 0 0 1 L_a.jpg\n"
               "\n"                                           # no 2D points
               "2 1 0 0 0 1 2 3 1 L_b.jpg\n"
               "10 20 5 11 21 -1 12 22 7\n"
               "3 1 0 0 0 0 0 0 1 S_a.jpg\n"
               "\n")
        p = Path(tempfile.mkdtemp()) / "images.txt"
        p.write_text(txt)
        imgs = mp.read_images_txt(p)
        self.assertEqual(sorted(imgs), ["L_a.jpg", "L_b.jpg", "S_a.jpg"])
        self.assertEqual((imgs["L_a.jpg"]["obs"], imgs["L_b.jpg"]["obs"], imgs["S_a.jpg"]["obs"]), (0, 2, 0))
        np.testing.assert_allclose(imgs["L_b.jpg"]["t"], [1, 2, 3])


class TextWriters(unittest.TestCase):
    def test_numpy_scalars_are_written_as_plain_numbers(self):
        q, t = mp.colmap_pose(np.eye(4))
        line = mp.image_lines(np.int64(3), q, t, 1, "L_a.jpg")
        self.assertNotIn("np.", line)
        head, pts, end = line.split("\n")
        self.assertEqual((pts, end), ("", ""))
        self.assertEqual([float(x) for x in head.split()[1:8]], list(q) + list(t))
        cam = mp.camera_line(1, 738, 994, np.float64(808.6), np.float64(808.4), np.float64(367.4), np.float64(504.1))
        self.assertEqual(cam, "1 PINHOLE 738 994 808.6 808.4 367.4 504.1\n")


class Splits(unittest.TestCase):
    def test_test_sets_need_both_datasets_and_train_needs_points(self):
        long_names = [mp.image_name("L", f"f{i}") for i in range(6)]
        short_names = [mp.image_name("S", f"f{i}") for i in range(3)]
        reg = {n: {"obs": 5} for n in long_names[:5] + short_names[:2]}
        reg[long_names[1]]["obs"] = 0                      # registered but sees no point
        both = set(long_names[:4]) | {short_names[0]}      # the other dataset lost some
        s = mp.build_splits(long_names, ["f2", "f4"], short_names, reg, both)
        self.assertEqual(s["train"], [long_names[0], long_names[3]])
        self.assertEqual(s["dropped_train_no_points"], [long_names[1]])
        self.assertEqual(s["val"], [long_names[2]])        # f4 is not in both
        self.assertEqual(s["xseq"], [short_names[0]])


class Alignment(unittest.TestCase):
    def test_umeyama_recovers_similarity(self):
        rng = np.random.default_rng(1)
        A = rng.normal(size=(50, 3))
        R = random_rotation(rng)
        B = (2.5 * (R @ A.T)).T + np.array([1.0, -2.0, 0.5])
        s, R2, t = mp.umeyama(A, B)
        self.assertAlmostEqual(s, 2.5, places=9)
        np.testing.assert_allclose(R2, R, atol=1e-9)
        np.testing.assert_allclose(t, [1.0, -2.0, 0.5], atol=1e-9)

    def test_pose_agreement_is_zero_for_a_scaled_copy(self):
        rng = np.random.default_rng(2)
        ref, est = {}, {}
        for i in range(10):
            R = random_rotation(rng)
            C = rng.normal(size=3)
            ref[str(i)] = {"q": mp.rot_to_qvec(R), "t": -R @ C}
            est[str(i)] = {"q": mp.rot_to_qvec(R), "t": -R @ (0.3 * C)}   # SfM: arbitrary scale
        agree = mp.pose_agreement(ref, est)
        self.assertEqual(agree["common_images"], 10)
        self.assertLess(agree["max_m"], 1e-9)


if __name__ == "__main__":
    unittest.main()
