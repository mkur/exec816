"""The package boundary must reject writes outside the program's allocation."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_program import image_regions, xex_segment


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.labels = {"stack_overflow": 0x3C00}
        self.image = {
            "format": "actionc-65816-image", "version": 2, "target": "wdc-65816-native",
            "abi": "action65816.native.v2", "entry": 0x6000, "stack_overflow": 0x3C00,
            "task_headroom": 26, "irq_headroom": 13,
            "segments": [{"address": 0x6000, "bytes": [0x6B], "writable": False, "executable": True}],
            "zero_fill": [{"address": 0x8000, "size": 3, "writable": True}],
            "routines": [{"address": 0x6000, "arguments": [], "result_bytes": 0}],
            "data": [], "imports": [],
        }

    def validate(self, image):
        # This synthetic geometry fixture deliberately describes the v2 format.
        return image_regions(image, self.labels, [], image_version=2)

    def test_explicit_zero_fill_and_exact_xex_bytes(self):
        regions = self.validate(self.image)
        self.assertEqual(regions, [(0x6000, b"\x6b"), (0x8000, b"\x00\x00\x00")])
        self.assertEqual(xex_segment(*regions[1]), b"\x00\x80\x02\x80\x00\x00\x00")

    def test_stack_check_setting_must_match_platform(self):
        image = copy.deepcopy(self.image)
        for invalid in (False, 0, 1, None, 'false'):
            image['stack_checks'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.validate(image)
        image['stack_checks'] = False
        image_regions(image, self.labels, [], image_version=2, stack_checks=False)
        with self.assertRaises(RuntimeError):
            image_regions(self.image, self.labels, [], image_version=2, stack_checks=False)

    def test_rejects_aliasing_platform_and_nonzero_banks(self):
        for address in (0x2200, 0x3000, 0x47FF, 0x5FFF, 0x9000, 0x18000, -1):
            with self.subTest(address=address):
                image = copy.deepcopy(self.image)
                image["zero_fill"][0]["address"] = address
                with self.assertRaises(RuntimeError):
                    self.validate(image)

    def test_rejects_overlap_overflow_and_invalid_payloads(self):
        for change in (
            lambda i: i["zero_fill"][0].update(address=0x6000),
            lambda i: i["zero_fill"][0].update(address=0x8FFF, size=2),
            lambda i: i["zero_fill"][0].update(size=0x100000000),
            lambda i: i["segments"][0].update(bytes=[]),
            lambda i: i["segments"][0].update(bytes=[256]),
            lambda i: i["segments"][0].update(bytes=[True]),
            lambda i: i["segments"][0].update(writable=True),
            lambda i: i.update(entry=0x8000),
            lambda i: i.update(entry=0x16000),
            lambda i: i.update(version=1),
            lambda i: i.update(abi="other"),
            lambda i: i.update(stack_overflow=0x4000),
            lambda i: i.update(imports=[{"address": 0xD000}]),
            lambda i: i.update(task_headroom=512),
            lambda i: i["routines"][0].update(arguments=[{"size": 2}]),
            lambda i: i["routines"][0].update(result_bytes=2),
        ):
            image = copy.deepcopy(self.image)
            change(image)
            with self.subTest(image=image):
                with self.assertRaises(RuntimeError):
                    self.validate(image)


if __name__ == "__main__":
    unittest.main()
