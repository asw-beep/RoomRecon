"""scripts/gpu.py: parsing and pinning, including the multi-GPU case that broke T2 run 1."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import gpu  # noqa: E402

# Shapes as nvidia-smi prints them. T4 x2 is what Kaggle's "T4" accelerator actually is.
ONE = "0, GPU-aaaa1111, NVIDIA GeForce RTX 3050 Laptop GPU, 6144, 1389, 8.6, 581.86\n"
TWO = ("0, GPU-aaaa1111, Tesla T4, 15360, 0, 7.5, 580.159.04\n"
       "1, GPU-bbbb2222, Tesla T4, 15360, 0, 7.5, 580.159.04\n")


class ParseInventory(unittest.TestCase):
    def test_single_gpu(self):
        (g,) = gpu.parse_inventory(ONE)
        self.assertEqual((g["index"], g["vram_total_mib"], g["compute_cap"]), (0, 6144, "8.6"))

    def test_two_gpus_are_two_records(self):
        gpus = gpu.parse_inventory(TWO)
        self.assertEqual([g["index"] for g in gpus], [0, 1])
        self.assertEqual([g["uuid"] for g in gpus], ["GPU-aaaa1111", "GPU-bbbb2222"])

    def test_blank_lines_ignored(self):
        self.assertEqual(len(gpu.parse_inventory("\n" + TWO + "\n\n")), 2)

    def test_empty_output_is_no_gpus(self):
        self.assertEqual(gpu.parse_inventory(""), [])

    def test_malformed_output_raises_instead_of_guessing(self):
        with self.assertRaises(ValueError):
            gpu.parse_inventory("0, Tesla T4, 15360\n")
        with self.assertRaises(ValueError):
            gpu.parse_inventory("[N/A], GPU-x, Tesla T4, 15360, 0, 7.5, 580\n")


class Select(unittest.TestCase):
    gpus = gpu.parse_inventory(TWO)

    def test_default_is_first(self):
        self.assertEqual(gpu.select(self.gpus, visible="")["index"], 0)

    def test_by_index(self):
        self.assertEqual(gpu.select(self.gpus, visible="1")["index"], 1)

    def test_by_uuid_and_prefix(self):
        self.assertEqual(gpu.select(self.gpus, visible="GPU-bbbb2222")["index"], 1)
        self.assertEqual(gpu.select(self.gpus, visible="GPU-bbbb")["index"], 1)

    def test_first_of_list(self):
        self.assertEqual(gpu.select(self.gpus, visible="GPU-bbbb2222,0")["index"], 1)

    def test_no_match_is_none_not_a_wrong_gpu(self):
        self.assertIsNone(gpu.select(self.gpus, visible="7"))
        self.assertIsNone(gpu.select([], visible=""))


class Describe(unittest.TestCase):
    def test_records_all_gpus_and_the_used_one(self):
        gpus = gpu.parse_inventory(TWO)
        d = gpu.describe(gpus, gpus[1])
        self.assertEqual(d["gpus_present"], 2)
        self.assertEqual(d["gpu_used"], {"index": 1, "uuid": "GPU-bbbb2222", "name": "Tesla T4"})
        self.assertNotIn("vram_used_mib", d["gpus"][0])   # a snapshot value, not hardware


if __name__ == "__main__":
    unittest.main()
