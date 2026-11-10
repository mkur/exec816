"""Exposure coverage must survive legal changes in GUI delivery timing."""
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]/'tools'))
from aes_exposure_oracle import check_exposure_rectangles


class ExposureOracleTests(unittest.TestCase):
    work=(40,35,464,171)

    def test_valid_coalescing(self):
        for rows in (
            [(72,43,352,48)],
            [(72,43,32,48),(120,43,304,48)],
            [(72,43,80,48),(392,43,32,48)],
            [(392,43,32,48),(120,43,32,48),(72,43,32,48)],
        ):
            with self.subTest(rows=rows):check_exposure_rectangles(rows,self.work)

    def test_missing_exposure(self):
        for rows in ([],[(72,43,80,48)],[(120,43,304,48)]):
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):
                check_exposure_rectangles(rows,self.work)

    def test_wrong_or_unbounded_damage(self):
        for rows in ([(72,43,352,47)],[(40,35,464,171)],
                     [(72,43,352,48)]*2,[(73,43,351,48)]):
            with self.subTest(rows=rows),self.assertRaises(RuntimeError):
                check_exposure_rectangles(rows,self.work)
