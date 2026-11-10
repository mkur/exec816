import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]/'tools'))
from gem_first_observe import digit_pixels, progress


def samples():
    before = dict(clients=[dict(identity=i, base=i*65536, id=i, window=i,
                                count=1, paints=2, digits_sha256='first') for i in (1, 2)])
    after = deepcopy(before)
    for row in after['clients']:
        row.update(count=3, paints=4, digits_sha256='second')
    return before, after


class GemFirstObserverTests(unittest.TestCase):
    def test_both_private_clients_must_advance_and_change_pixels(self):
        self.assertEqual([r['increments'] for r in progress(*samples())], [2, 2])
        for field in ('count', 'paints', 'digits_sha256'):
            before, after = samples()
            after['clients'][0][field] = before['clients'][0][field]
            with self.assertRaises(RuntimeError):
                progress(before, after)

    def test_duplicate_or_replaced_identity_is_not_independent_progress(self):
        for field in ('identity', 'base', 'id', 'window'):
            before, after = samples()
            before['clients'][1][field] = before['clients'][0][field]
            with self.assertRaises(RuntimeError):
                progress(before, after)
            before, after = samples()
            after['clients'][0][field] += 1
            with self.assertRaises(RuntimeError):
                progress(before, after)

    def test_digit_crop_accounts_for_margin_and_excludes_alpha(self):
        raw = bytearray(672*240*4)
        raw[(11*672+16+7)*4:(11*672+16+7)*4+4] = b'RGBa'
        cropped = digit_pixels(raw, 672*4, 672, 240, 7, 11)
        self.assertEqual(cropped[:3], b'RGB')
        self.assertEqual(cropped[3:], bytes(48*8*3-3))
        with self.assertRaises(RuntimeError):
            digit_pixels(raw, 672*4, 672, 240, 600, 239)
