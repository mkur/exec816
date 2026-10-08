"""Per-admission attribution must retain deferral and ignore other Tasks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from presenter_control_trace import admissions, summarize


class PresenterControlTraceTests(unittest.TestCase):
    def test_completed_deferred_and_unobserved_requests(self):
        definition = dict(points=dict(native_operation_pump_0=0x100,
                                      native_operation_dispatch_0=0x200,
                                      native_deferred=0x300))
        def event(tick, pc, a, dp=0x1100):
            return tick, ['cpu', '0', '0', '0', f'{pc:x}', f'{a:x}',
                          '0', '0', '0', f'{dp:x}']
        def span(start, end, admitted=1):
            return dict(kind='deskcore_pump', start=start, end=end,
                        return_a=admitted, charged_cpu_ms=end-start)
        events = [event(1, 0x100, 0xff07), event(2, 0x300, 0),
                  event(5, 0x200, 14, dp=0x1200), event(6, 0x200, 0xab07),
                  event(7, 0x200, 7)]
        rows = admissions(events, definition,
                          [span(0, 4), span(4, 8), span(8, 9, 0), span(9, 10)],
                          0x1100)
        self.assertEqual([r['operation_name'] for r in rows],
                         ['FOCUS', 'FOCUS', 'unobserved'])
        summary = summarize(rows)
        self.assertEqual(summary['FOCUS']['calls'], 2)
        self.assertEqual(summary['FOCUS']['deferred'], 1)
        self.assertEqual(summary['FOCUS']['total_cpu_ms'], 8)

    def test_changed_opcode_is_rejected(self):
        definition = dict(points=dict(native_operation_pump_0=1, native_deferred=2))
        events = [(i, ['cpu', '0', '0', '0', '1', str(i), '0', '0', '0', '1100'])
                  for i in (1, 2)]
        with self.assertRaisesRegex(RuntimeError, 'Opcode changed'):
            admissions(events, definition,
                       [dict(kind='deskcore_pump', start=0, end=3, return_a=1)],
                       0x1100)
