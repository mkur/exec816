"""Missing scheduler evidence and nested caller costs must fail or reconcile."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from aes_timing_breakdown import input_breakdown, caller_breakdown, scheduler_states, io_breakdown
from sio_transaction_trace import BASE_HZ
from compare_aes_diagnostics import compare


def event(t, pc, dp=0xb00, a=0, x=0):
    return t, ['cpu', '0', '0', '8', hex(pc), hex(a), hex(x), '0', '0', hex(dp)]


SCHEDULER = dict(points=dict(ready_low=1, ready_high=2, ready=3, blocked=4),
                 selected=5, context_base=0x3f0000, context_stride=64,
                 task_dps=[0xb00, 0xc00])


def fixture():
    events = [event(0, 5), event(1, 4), event(2, 5, dp=0xc00),
              event(5, 1, a=0), event(6, 2, a=0x3f00), event(7, 3),
              event(10, 5), event(15, 6), event(16, 9)]
    profile = dict(worker_dp=0xb00, segments=[
        (0, 1, 0xb00, False), (1, 2, 0xb00, False),
        (2, 5, 0xc00, False), (5, 6, 0xc00, False),
        (6, 7, 0xc00, False), (7, 10, 0xc00, False),
        (10, 15, 0xb00, False), (15, 16, 0xb00, False)])
    return events, profile


class AESTimingBreakdownTests(unittest.TestCase):
    def test_timer_exit_continuation_covers_tail_poll_and_direct_return(self):
        definitions = dict(
            dispatch=dict(entry=20, returns=[21], category='native_dispatch'),
            leave=dict(entry=30, returns=[31], category='timer_exit'),
            poll=dict(entry=40, returns=[41], category='timer_poll'))
        sites = {10: dict(end=14, category='device_io', callee='SendIO')}
        calls = [dict(dp=0xb00, start=0, client=9)]
        segments = [(0, 9, 0xb00, False)]
        common = [event(0, 10), event(1, 20), event(2, 30)]
        tail = [event(3, 40), event(6, 41)]
        end = [event(7, 31), event(8, 21), event(9, 14)]
        for middle, expected_exit in [(tail, 2), ([], 5)]:
            row = io_breakdown(common+middle+end, definitions, sites, segments, calls)['records'][0]
            self.assertAlmostEqual(row['exclusive_cpu_ms']['timer_exit']*BASE_HZ/1000, expected_exit)
            self.assertAlmostEqual(sum(row['exclusive_cpu_ms'].values())*BASE_HZ/1000, 9)
            leave = next(h for h in row['helpers'] if h['name'] == 'leave')
            self.assertAlmostEqual(leave['charged_cpu_ms']*BASE_HZ/1000, 5)

    def test_io_categories_keep_gateway_cpu_but_exclude_interrupts_and_peers(self):
        definitions = dict(
            dispatch=dict(entry=20, returns=[21], category='native_dispatch'),
            gateway=dict(entry=30, returns=[31], category='io_gateway'))
        sites = {10: dict(end=14, category='device_io', callee='DoIO')}
        events = [event(0, 10), event(1, 20), event(2, 30),
                  event(3, 99, dp=0xa00), event(8, 31), event(9, 21), event(10, 14)]
        segments = [(0, 3, 0xb00, False), (3, 4, 0xb00, True),
                    (4, 6, 0xc00, False), (6, 10, 0xb00, False)]
        calls = [dict(dp=0xb00, start=0, client=10)]
        row = io_breakdown(events, definitions, sites, segments, calls)['records'][0]
        self.assertAlmostEqual(row['exclusive_cpu_ms']['c_wrapper']*BASE_HZ/1000, 2)
        self.assertAlmostEqual(row['exclusive_cpu_ms']['native_dispatch']*BASE_HZ/1000, 2)
        self.assertAlmostEqual(row['exclusive_cpu_ms']['io_gateway']*BASE_HZ/1000, 3)
        self.assertAlmostEqual(row['off_cpu_ms']*BASE_HZ/1000, 2)
        self.assertAlmostEqual(row['interrupt_ms']*BASE_HZ/1000, 1)
        with self.assertRaisesRegex(RuntimeError, 'Incomplete I/O helper'):
            io_breakdown(events[:-2], definitions, sites, segments, calls)
        with self.assertRaisesRegex(RuntimeError, 'Missing I/O helper entry'):
            io_breakdown(events[:2]+events[3:], definitions, sites, segments, calls)
        with self.assertRaisesRegex(RuntimeError, 'Missing native dispatch'):
            io_breakdown([events[0], events[-1]], definitions, sites, segments, calls)

    def test_io_helpers_remain_separate_when_two_tasks_overlap(self):
        definitions = dict(dispatch=dict(entry=20, returns=[21], category='native_dispatch'))
        sites = {10: dict(end=14, category='device_io', callee='CheckIO')}
        events = [event(0, 10), event(1, 20), event(2, 10, dp=0xc00),
                  event(3, 20, dp=0xc00), event(4, 21, dp=0xc00),
                  event(5, 14, dp=0xc00), event(6, 21), event(7, 14)]
        segments = [(0, 2, 0xb00, False), (2, 5, 0xc00, False), (5, 7, 0xb00, False)]
        calls = [dict(dp=0xb00, start=0, client=7), dict(dp=0xc00, start=2, client=5)]
        rows = io_breakdown(events, definitions, sites, segments, calls)['records']
        self.assertEqual(len(rows), 2)
        for row in rows:
            expected = 4 if row['dp'] == 0xb00 else 3
            self.assertAlmostEqual(row['charged_cpu_ms']*BASE_HZ/1000, expected)
            self.assertEqual(len(row['helpers']), 1)

    def test_blocked_ready_selected_and_cpu_are_distinct(self):
        events, profile = fixture()
        row = input_breakdown(events, SCHEDULER, profile,
                              [dict(capture=3, observed=16)], 6)['records'][0]
        scale = BASE_HZ/1000
        for key, ticks in [('capture_to_ready_ms', 4), ('ready_to_selected_ms', 3),
                           ('selected_to_consume_ms', 5), ('runnable_off_cpu_ms', 3),
                           ('blocked_off_cpu_ms', 4), ('charged_cpu_ms', 5)]:
            self.assertAlmostEqual(row[key]*scale, ticks)

    def test_already_ready_does_not_wait_for_another_wake(self):
        events, profile = fixture()
        row = input_breakdown(events, SCHEDULER, profile,
                              [dict(capture=8, observed=16)], 6)['records'][0]
        self.assertEqual(row['presenter_state_at_capture'], 'ready')
        self.assertEqual(row['ready'], 8)
        self.assertEqual(row['selected'], 10)

    def test_already_selected_has_zero_initial_scheduling_delay(self):
        events, profile = fixture()
        row = input_breakdown(events, SCHEDULER, profile,
                              [dict(capture=11, observed=16)], 6)['records'][0]
        self.assertEqual(row['ready'], 11)
        self.assertEqual(row['selected'], 11)
        self.assertEqual(row['elapsed_ms'], row['charged_cpu_ms'])

    def test_missing_ready_pointer_and_selection_fail_closed(self):
        events, profile = fixture()
        with self.assertRaisesRegex(RuntimeError, 'Missing Ready context'):
            scheduler_states([e for e in events if int(e[1][4], 16) != 2], SCHEDULER, 5)
        with self.assertRaisesRegex(RuntimeError, 'Missing presenter selection'):
            input_breakdown([e for e in events if e[0] != 10], SCHEDULER, profile,
                            [dict(capture=3, observed=16)], 6)

    def test_consumption_outside_sample_is_rejected(self):
        events, profile = fixture()
        with self.assertRaisesRegex(RuntimeError, 'outside observed'):
            input_breakdown(events, SCHEDULER, profile, [dict(capture=3, observed=14)], 6)

    def test_later_preemption_is_not_hidden_by_zero_first_selection_delay(self):
        events, profile = fixture()
        events = [e for e in events if e[0] < 15]+[
            event(11,1,a=0),event(12,2,a=0x3f00),event(13,3),
            event(14,5,dp=0xc00),event(20,5),event(22,6),event(23,9)]
        profile['segments'] = profile['segments'][:-2]+[
            (10,11,0xb00,False),(11,12,0xb00,False),(12,13,0xb00,False),
            (13,14,0xb00,False),(14,20,0xc00,False),(20,22,0xb00,False),(22,23,0xb00,False)]
        row = input_breakdown(events,SCHEDULER,profile,[dict(capture=10,observed=23)],6)['records'][0]
        self.assertEqual(row['ready_to_selected_ms'],0)
        self.assertAlmostEqual(row['runnable_off_cpu_ms']*BASE_HZ/1000,6)

    def test_nested_calls_charge_innermost_category_and_exclude_peer(self):
        sites = {10: dict(end=14, category='clock', callee='Read'),
                 20: dict(end=24, category='device_io', callee='DoIO')}
        events = [event(1, 10), event(3, 20), event(8, 24), event(10, 14)]
        segments = [(0, 4, 0xb00, False), (4, 7, 0xc00, False),
                    (7, 9, 0xb00, False), (9, 10, 0xb00, True), (10, 12, 0xb00, False)]
        rows = caller_breakdown(events, sites, segments,
                               [dict(start=0, client=12, dp=0xb00, operation=25)])['records']
        row = rows[0]
        scale = BASE_HZ/1000
        self.assertAlmostEqual(row['exclusive_cpu_ms']['clock']*scale, 3)
        self.assertAlmostEqual(row['exclusive_cpu_ms']['device_io']*scale, 2)
        self.assertAlmostEqual(row['exclusive_cpu_ms']['other']*scale, 3)
        self.assertAlmostEqual(row['off_cpu_ms']*scale, 3)
        self.assertAlmostEqual(row['interrupt_ms']*scale, 1)
        with self.assertRaisesRegex(RuntimeError, 'Incomplete caller-cost'):
            caller_breakdown(events[:-1], sites, segments, [])

    def test_concurrent_tasks_do_not_share_helper_stacks(self):
        sites = {10: dict(end=14, category='binding', callee='Context')}
        events = [event(0, 10), event(1, 10, dp=0xc00),
                  event(3, 14, dp=0xc00), event(5, 14)]
        segments = [(0, 1, 0xb00, False), (1, 3, 0xc00, False), (3, 5, 0xb00, False)]
        rows = caller_breakdown(events, sites, segments,
            [dict(start=0, client=5, dp=0xb00, operation=12),
             dict(start=1, client=3, dp=0xc00, operation=25)])['records']
        self.assertAlmostEqual(rows[0]['charged_cpu_ms']*BASE_HZ/1000, 3)
        self.assertAlmostEqual(rows[1]['charged_cpu_ms']*BASE_HZ/1000, 2)

    def test_equal_offer_comparison_rejects_missing_work_but_keeps_backlog(self):
        report = dict(status='pass', diagnostic_only=True, frames=40, samples=[],
            machine={'video':'PAL'}, load='idle', xex_sha256='image', progress={},
            offered_load=dict(start_frame=100, period_frames=20, offered=2, started=2,
                completed=1, pending=1, drained=2, offers=[{'frame':100}, {'frame':120}]),
            caller_breakdown=dict(records=[],summary={}))
        peer = deepcopy(report)
        peer['load'] = 'disk'
        self.assertEqual(compare([report,peer])['cohorts'][1]['pending'], 1)
        peer['offered_load']['offers'][1]['frame'] = 121
        with self.assertRaisesRegex(RuntimeError, 'missing offers'):
            compare([report,peer])
        peer = deepcopy(report)
        peer['offered_load']['drained'] = 1
        with self.assertRaisesRegex(RuntimeError, 'lost outstanding'):
            compare([report,peer])
        peer = deepcopy(report)
        peer['machine']['video'] = 'NTSC'
        with self.assertRaisesRegex(RuntimeError, 'machine differs'):
            compare([report,peer])
