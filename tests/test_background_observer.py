"""Negative controls for the emitted background observer's coverage checks."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from test_desktop_background import CLIENT, DAMAGE, check_fills


class BackgroundCoverageTests(unittest.TestCase):
    def rows(self):
        rows = [dict(fills=[]) for _ in range(9)]
        rows[1]['fills'] = [dict(bounds=CLIENT, pen=3), dict(bounds=(31, 29, 191, 45), pen=8)]
        rows[5]['fills'] = [dict(bounds=DAMAGE[0], pen=3)]
        return rows

    def test_complete_client_and_bounded_sparse_fill(self):
        check_fills(self.rows())

    def test_duplicate_client_pass_is_rejected(self):
        rows = self.rows()
        rows[1]['fills'].append(copy.deepcopy(rows[1]['fills'][0]))
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            check_fills(rows)

    def test_frame_overdraw_is_rejected(self):
        rows = self.rows()
        rows[1]['fills'][1]['bounds'] = (31, 29, 191, 46)
        with self.assertRaisesRegex(RuntimeError, 'Frame background'):
            check_fills(rows)

    def test_sparse_fill_cannot_escape_damage(self):
        rows = self.rows()
        rows[5]['fills'].append(dict(bounds=(0, 0, 1, 1), pen=8))
        with self.assertRaisesRegex(RuntimeError, 'escaped'):
            check_fills(rows)
