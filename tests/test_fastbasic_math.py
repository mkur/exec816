import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from generate_fastbasic_math import number


class AtariNumberTests(unittest.TestCase):
    def test_independent_six_byte_vectors(self):
        for text, expected in {
            '0': '000000000000', '1': '400100000000',
            '-1': 'c00100000000', '.1': '3f1000000000',
            '23.5': '402350000000', '65536': '420655360000',
            '4294967296': '444294967296',
            '2.302585092994045684': '400230258509',
        }.items():
            with self.subTest(text=text):
                self.assertEqual(number(text), bytes.fromhex(expected))

    def test_decimal_rounding_and_mantissa_carry(self):
        self.assertEqual(number('1.234567895'), bytes.fromhex('400123456790'))
        self.assertEqual(number('99.999999995'), bytes.fromhex('410100000000'))


if __name__ == '__main__':
    unittest.main()
