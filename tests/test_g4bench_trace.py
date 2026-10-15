import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from g4bench_trace import calls, clock_tick_bounds, listing_returns, native_calls, partition, read_trace
from sio_transaction_trace import BASE_HZ


def event(tick, pc, stack, dp=0x1100, argument=0):
    return tick, ['cpu', '0', '0', '8', f'{pc:x}', f'{argument:x}', '0', '0',
                  f'{stack:x}', f'{dp:x}']


class BenchmarkTrace(unittest.TestCase):
    def test_clock_check_uses_actual_vbis_not_nominal_fifty_hz(self):
        # 114 PAL frames take about 2286 ms; a further fractional frame can
        # exceed the former 22 ms tolerance around nominal ticks/50.
        frame=35568
        vbis=[n*frame for n in range(120)]
        start=frame+100
        end=115*frame+frame-100
        clocks=[dict(start=start-20,end=start),dict(start=end,end=end+20)]
        lower,upper=clock_tick_bounds(clocks,vbis)
        self.assertLessEqual(lower,114)
        self.assertGreaterEqual(upper,114)
        self.assertLess(upper,117)

    def test_clock_read_preemption_is_part_of_snapshot_uncertainty(self):
        vbis=list(range(0,101,10))
        clocks=[dict(start=1,end=32),dict(start=61,end=65)]
        # The first snapshot can precede three ticks spent inside its call.
        self.assertEqual(clock_tick_bounds(clocks,vbis),(2,7))

    def test_tail_call_and_callback_returns_use_full_stack_and_task(self):
        entries = {10: 'outer', 20: 'tail', 30: 'callback'}
        events = [event(0, 10, 0x4510, argument=2), event(1, 20, 0x4510),
                  event(2, 30, 0x4410), event(3, 90, 0x4513, dp=0x1200),
                  event(4, 90, 0x4413), event(5, 90, 0x4513)]
        rows, unfinished = calls(events, entries, {90}, 0x1100)
        self.assertFalse(unfinished)
        self.assertEqual([(r['kind'], r['start'], r['end']) for r in rows],
                         [('callback', 2, 4), ('outer', 0, 5), ('tail', 1, 5)])
        self.assertEqual(rows[1]['argument'], 2)

    def test_loaded_c_caller_needs_only_the_resident_rtl(self):
        # The return address in a loaded app need not be among resident JSLs.
        events = [event(0, 10, 0x4510), event(1, 20, 0x4510),
                  event(2, 40, 0x4510, argument=1),
                  event(3, 10, 0x4510), event(4, 40, 0x4510, argument=0)]
        rows, unfinished = calls(events, {10:'public',20:'tail'}, set(),
                                 0x1100, {40})
        self.assertFalse(unfinished)
        self.assertEqual([(r['kind'],r['start'],r['end'],r['return_a']) for r in rows],
                         [('public',0,2,1),('tail',1,2,1),('public',3,4,0)])

    def test_native_policy_calls_remain_separate_across_tasks(self):
        events = [event(0,10,0x4510), event(1,10,0x4510,dp=0x1200),
                  event(2,40,0x4510,dp=0x1200,argument=0),
                  event(3,40,0x4510,argument=1)]
        rows = native_calls(events, {'policy':dict(entry=10,returns=[40])})
        self.assertEqual([(r['dp'],r['start'],r['end'],r['return_a']) for r in rows],
                         [(0x1200,1,2,0),(0x1100,0,3,1)])

    def test_truncated_call_is_reported(self):
        rows, unfinished = calls([event(0, 10, 0x4510)], {10:'outer'}, {90}, 0x1100)
        self.assertFalse(rows)
        self.assertEqual(unfinished[0]['kind'], 'outer')

    def test_missing_return_cannot_silently_join_two_invocations(self):
        with self.assertRaisesRegex(RuntimeError, 'without a matched return'):
            calls([event(0, 10, 0x4510), event(1, 10, 0x4510)],
                  {10:'outer'}, {90}, 0x1100)

    def test_exclusive_costs_remove_nested_upload_waits_and_preemption(self):
        timeline = Timeline([(0, 10, 1, False), (10, 20, 2, False),
                             (20, 30, 1, True), (30, 50, 1, False)], 1)
        spans = [dict(kind='GemDrawingBorrow', start=0, end=50),
                 dict(kind='text_run', start=5, end=45),
                 dict(kind='_VbxeTextUpload', start=6, end=8),
                 dict(kind='idle', start=8, end=35)]
        costs = partition(timeline, spans, 0, 50)
        expected = {'borrow_setup_cursor':10, 'command_build':11,
                    'upload':2, 'completion_poll':7}
        self.assertEqual(set(costs), set(expected))
        for name, ticks in expected.items():
            self.assertAlmostEqual(costs[name], ticks/BASE_HZ*1000)
        self.assertAlmostEqual(sum(costs.values()), 30/BASE_HZ*1000)

    def test_call_operand_is_never_treated_as_another_instruction(self):
        listing = '''.section farcode,text
    \\ 000000 22......             jsl long:helper
    \\ 000004 6b                   rtl
'''
        image = dict(segments=[dict(address=0x10000, executable=True,
                                    bytes=[0x22, 0x22, 0x34, 0x12, 0x6b])])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path/'probe.lst').write_text(listing.replace('\n', '\r\n'))
            self.assertEqual(listing_returns(image, path), [0x10004])
            self.assertEqual(listing_returns(image, path, exits=True), [0x10004])

    def test_streaming_trace_keeps_matching_returns_and_clock_wrap(self):
        definition = dict(link_base=0, resident_entries={20:'nested'},
                          app_entries={10:'BenchDraw'}, resident_returns=[90],
                          app_returns=[91], timeline=dict(points=dict(selected=100,
                              native_irq=110, native_nmi=120)))
        observed = [event(0, 100, 0x4510), event(1, 10, 0x4510),
                    event(2, 90, 0x4000), event(3, 20, 0x4410),
                    event(4, 90, 0x4413, dp=0x1200), event(5, 90, 0x4413),
                    event(6, 91, 0x4513)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'trace.log'
            with path.open('w') as out:
                out.write('[SIOTXN] anchor 4294967296\n')
                for tick, fields in observed:
                    fields[1] = str(tick)
                    out.write('[SIOTXN] '+' '.join(fields)+'\n')
            selected = read_trace(path, definition, dict(base=0))
        self.assertEqual([t for t, _ in selected],
                         [4294967296+i for i in (0, 1, 3, 5, 6)])


if __name__ == '__main__':
    unittest.main()
