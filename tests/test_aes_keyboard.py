"""Independent named-key checks for the generated Atari/GEM translation data."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import generate_aes_keyboard as generator


class KeyboardMapping(unittest.TestCase):
    def test_generated(self):
        self.assertEqual(generator.OUTPUT.read_text(), generator.render())

    def test_named_keys(self):
        mapping = json.loads(generator.INPUT.read_text())
        specials = mapping['atascii_to_gem']
        for atascii, gem in ((155, 0x1c0d), (27, 0x011b), (30, 0x4b00),
                             (31, 0x4d00), (28, 0x4800), (29, 0x5000),
                             (126, 0x0e08), (254, 0x537f)):
            self.assertEqual(specials[str(atascii)], gem)
        for atari, st in ((63, 0x1e), (18, 0x2e), (44, 0x0f), (33, 0x39)):
            self.assertEqual(mapping['scan_codes'][atari], st)
        self.assertEqual(mapping['policy']['tab_all_modifiers'], 0x0f09)


if __name__ == '__main__':
    unittest.main()
