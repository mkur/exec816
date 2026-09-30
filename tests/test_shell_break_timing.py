import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from shell_break_timing import LIMITS, validate
from sio_transaction_trace import BASE_HZ


class ShellBreakTimingTests(unittest.TestCase):
    def setUp(self):
        tick=BASE_HZ/1000
        self.timing = dict(capture=0, durable=100*tick, retained=400*tick, physical=480*tick, usable=500*tick,
                          queued_publication=100*tick,queued_reply=350*tick,
                          delivery_ms=100, queued_reply_ms=250, prompt_ms=500)

    def test_accepts_inclusive_bounds(self):
        validate(self.timing, queued=True)

    def test_rejects_each_missed_or_missing_bound(self):
        for name, limit in LIMITS.items():
            with self.subTest(name=name):
                for bad in (-1, limit + .001, float('nan')):
                    with self.assertRaises(ValueError):
                        validate(dict(self.timing, **{name: bad}), queued=True)
                missing = dict(self.timing)
                del missing[name]
                with self.assertRaises(ValueError):
                    validate(missing, queued=True)

    def test_requires_real_milestones_in_order(self):
        for name in ('capture', 'durable', 'retained', 'physical', 'usable'):
            bad = dict(self.timing)
            del bad[name]
            with self.assertRaises(ValueError):
                validate(bad)
        with self.assertRaises(ValueError):
            validate(dict(self.timing, retained=self.timing['physical']+1))
        with self.assertRaises(ValueError):
            validate(dict(self.timing, usable=self.timing['retained']-1))
        with self.assertRaises(ValueError):
            validate(dict(self.timing, usable=BASE_HZ*.501,prompt_ms=501))
