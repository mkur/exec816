import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_fastbasic import ABI, profile
from generate_fastbasic import products


class FastBasicProfileTests(unittest.TestCase):
    def capsule(self):
        return bytearray(struct.pack('<4s6H', b'FB65', ABI['version'],
            ABI['target'], ABI['load'], ABI['load']+1, ABI['load'], ABI['limit'])+b'\x60')

    def test_generated_contract(self):
        for path, expected in products().items():
            self.assertEqual(path.read_text(), expected, str(path))

    def test_fresh_programs_are_not_hash_allowlisted(self):
        first = self.capsule()
        second = self.capsule()
        second[-1] = 0xea
        self.assertEqual(profile(first), profile(second))

    def test_extents_and_provider_identity(self):
        original = self.capsule()
        malformed = [original[:15], original[:-1], original+b'\0']
        for offset, value in [(0,0), (4,2), (6,0), (8,0x80),
                              (10,0xffff), (12,0x100), (14,0xffff)]:
            changed = original.copy()
            struct.pack_into('<H', changed, offset, value)
            malformed.append(changed)
        for raw in malformed:
            with self.subTest(raw=raw.hex()), self.assertRaises(ValueError):
                profile(raw)


if __name__ == '__main__':
    unittest.main()
