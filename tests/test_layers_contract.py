"""Host checks for generated layouts and the independent region oracle."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import generate_layers
from test_layers import check_region, geometry_cases


class LayersTests(unittest.TestCase):
    def test_generated_layout(self):
        for path, content in generate_layers.files().items():
            self.assertEqual(path.read_text(), content)
        self.assertEqual(generate_layers.layout()['Rect']['size'], 8)
        self.assertEqual(generate_layers.layout()['Region']['size'], 770)

    def test_oracle_rejects_hole_and_duplicate(self):
        base = (0, 0, 10, 10)
        cut = (10, 0, 11, 10)
        check_region(struct.pack('<H4h', 1, *base), base, cut)
        with self.assertRaises(Exception):
            check_region(struct.pack('<H4h', 1, 0, 0, 9, 10), base, cut)
        with self.assertRaises(Exception):
            check_region(struct.pack('<H8h', 2, *base, *base), base, cut)

    def test_deterministic_cases(self):
        self.assertEqual(geometry_cases(), geometry_cases())
        self.assertEqual(len(geometry_cases()), 128)
