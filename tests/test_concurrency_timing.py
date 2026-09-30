"""Check timing interpretation independently of the guest/kernel implementation."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from test_signal_concurrency import masked_intervals, read_events, serial_timing


def mask(tick, masked, pc='010100'):
    return tick, ['mask', str(tick), '0', '8', pc, '04' if masked else '00',
                  '0', '0100ff', '78' if masked else '58', '0', '0']


def serial(late=False):
    # First byte shifts at 10; its next refill is just early or exactly late.
    refill = 150 if late else 149.875
    second = 164 if late else 150
    return [(0, ['write', '0', '0', '0', '0']),
            (10, ['ready', '10', '0', '14', '16']),
            (refill, ['write', str(refill), '1', '0', '0']),
            (second, ['ready', str(second), '1', '14', '16']),
            (second+140, ['idle', str(second+140)])]


class ConcurrencyTimingTests(unittest.TestCase):
    def test_mask_intervals_clip_boundaries_and_keep_short_irq_windows(self):
        trace = [mask(0, True), mask(10, False), mask(10.25, True),
                 mask(40, False), mask(50, True), mask(70, False)]
        result = masked_intervals(trace, 5, 60)
        self.assertEqual([(r['start_tick'], r['end_tick']) for r in result],
                         [(5, 10), (10.25, 40), (50, 60)])
        self.assertEqual([r['clipped'] for r in result], [True, False, True])

    def test_incomplete_or_duplicate_mask_trace_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'cover'):
            masked_intervals([mask(0, False), mask(5, True)], 1, 10)
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            masked_intervals([mask(0, True), mask(5, True), mask(20, False)], 1, 10)

    def test_cpu_and_mask_subcycles_survive_clock_wrap(self):
        text = ('private bridge chatter ignored\n'
                '[SIOPOC] write 4294967295 0 0 0\n'
                '[SIOPOC] mask 0 3 8 010100 04 0 0100ff 78 0 0\n'
                '[SIOPOC] cpu 1 7 8 010104 0000 0000 0000 4000 2200 00 04 0\n')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'trace.log'
            path.write_text(text)
            events = read_events(path)
        self.assertEqual([t for t, _ in events], [4294967295, 4294967296.375, 4294967297.875])

    def test_exact_deadline_is_a_miss_and_functional_bytes_do_not_imply_pass(self):
        timing, rows = serial_timing(serial(), 2)
        self.assertEqual(timing['verdict'], 'pass')
        self.assertEqual(rows[0]['latency_base_cycles'], 139.875)
        timing, _ = serial_timing(serial(late=True), 2)
        self.assertEqual((timing['verdict'], timing['deadline_misses'], timing['gaps']), ('fail', 1, 1))

    def test_instruction_status_cross_checks_transition_trace(self):
        text = ('[SIOPOC] mask 0 0 8 010100 04 0 0100ff 78 0 0\n'
                '[SIOPOC] cpu 1 0 8 010104 0000 0000 0000 4000 2200 00 00 0\n')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'trace.log'
            path.write_text(text)
            with self.assertRaisesRegex(RuntimeError, 'disagrees'):
                read_events(path)

    def test_corrupt_overwritten_and_incomplete_serial_streams_are_rejected(self):
        for change, message in (('sequence', 'transmitted'), ('overwrite', 'overwritten'), ('end', 'finish')):
            trace = serial()
            if change == 'sequence':
                trace[3][1][2] = '2'
            elif change == 'overwrite':
                trace[2][1][4] = '1'
            else:
                trace.pop()
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, message):
                serial_timing(trace, 2)


if __name__ == '__main__':
    unittest.main()
