import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from record_console_break import MATRIX,validate_matrix


class ConsoleBreakRecordTests(unittest.TestCase):
    def test_requires_complete_native_coverage(self):
        validate_matrix([list(case) for case in MATRIX])
        for index in range(len(MATRIX)):
            with self.subTest(case=MATRIX[index]):
                with self.assertRaises(RuntimeError):
                    validate_matrix(MATRIX[:index]+MATRIX[index+1:])
        with self.assertRaises(RuntimeError):
            validate_matrix(MATRIX[:-1]+[MATRIX[0]])
        with self.assertRaises(RuntimeError):
            validate_matrix(MATRIX+MATRIX[:1])
