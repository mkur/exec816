"""Per-admission attribution must retain deferral and ignore other Tasks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from presenter_control_trace import admissions, summarize, bookkeeping_costs
from console_turn_profile import Timeline
from sio_transaction_trace import BASE_HZ


class PresenterControlTraceTests(unittest.TestCase):
    def test_bookkeeping_unions_exclude_nested_double_charge_and_peer_time(self):
        timeline = Timeline([(0,10,0x1100,False),(10,20,0x1200,False),
                             (20,30,0x1100,True),(30,40,0x1100,False)],0x1100)
        spans = [dict(kind='DESKHOST_RUNNABLE',start=0,end=40,return_a=0),
                 dict(kind='DESKINPUT_RUNNABLE',start=5,end=35,return_a=0),
                 dict(kind='INPUT_TAKE',start=30,end=32,return_a=1)]
        result = bookkeeping_costs([],spans,timeline,0,40)
        unit = 1000/BASE_HZ
        self.assertAlmostEqual(result['group_cpu_ms']['readiness_checks'],20*unit)
        self.assertAlmostEqual(result['measured']['off_cpu_ms'],10*unit)
        self.assertAlmostEqual(result['measured']['interrupt_ms'],10*unit)
        self.assertEqual(result['routines']['INPUT_TAKE']['returns'],{'1':1})

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
