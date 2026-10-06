import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline, analyze_events
from sio_transaction_trace import BASE_HZ


def event(tick, pc, dp=0x1100, stack=0x4500):
    return tick, ['cpu', '0', '0', '8', f'{pc:x}', '0', '0', '0',
                  f'{stack:x}', f'{dp:x}']


DEFINITION = dict(points=dict(turn=10, selected=20, native_irq=30,
    native_nmi=40, interrupt_schedule=50, worker_retire=60),
    task_dps=[0x1100, 0x1200], spans={'text': dict(entry=70, returns=[80])})


class ConsoleTurnProfile(unittest.TestCase):
    def test_exclusive_time_sums_and_clipped_intervals(self):
        timeline = Timeline([(0, 10, 1, False), (10, 20, 2, False),
                             (20, 30, 1, True), (30, 40, 1, False)], 1)
        row = timeline.measure(5, 35)
        for key in ('charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms'):
            self.assertAlmostEqual(row[key], 10/BASE_HZ*1000)
        self.assertAlmostEqual(row['elapsed_ms'], sum(row[key] for key in
            ('charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')))

    def test_preempted_text_and_nested_interrupts_are_separate(self):
        events = [event(0, 20), event(1, 10), event(2, 70),
                  event(3, 30), event(4, 40, stack=0x4400),
                  event(5, 50, stack=0x4400-9), event(6, 50, stack=0x4500-9),
                  event(7, 20, dp=0x1200), event(17, 20), event(20, 80),
                  event(21, 10), event(22, 60)]
        result = analyze_events(events, DEFINITION)
        row = result['turns'][0]
        self.assertAlmostEqual(row['elapsed_ms'], 20/BASE_HZ*1000)
        self.assertAlmostEqual(row['off_cpu_ms'], 10/BASE_HZ*1000)
        self.assertAlmostEqual(row['interrupt_ms'], 3/BASE_HZ*1000)
        self.assertAlmostEqual(row['charged_cpu_ms'], 7/BASE_HZ*1000)
        self.assertAlmostEqual(result['routines']['text']['charged_cpu_ms']['total'],
                               5/BASE_HZ*1000)

    def test_missing_native_interrupt_exit_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            analyze_events([event(0, 20), event(1, 10), event(2, 10),
                            event(3, 30)], DEFINITION)

    def test_global_interrupt_time_includes_peer_irqs_and_clips_to_turns(self):
        events = [event(0, 20), event(1, 10), event(2, 70),
                  event(3, 20, dp=0x1200), event(4, 30, dp=0x1200),
                  event(8, 50, dp=0, stack=0x4500-9), event(9, 20),
                  event(10, 80), event(11, 10), event(12, 30),
                  event(14, 50, stack=0x4500-9), event(15, 60)]
        events[7][1][5:7] = ['fffe', 'ffff']
        result = analyze_events(events, DEFINITION)
        self.assertAlmostEqual(result['global_interrupt_ms'], 4/BASE_HZ*1000)
        self.assertEqual(result['turns'][0]['interrupt_ms'], 0)
        self.assertEqual(result['routine_spans'][0]['return_a'], 65534)
        self.assertEqual(result['routine_spans'][0]['return_x'], 65535)

    def test_breakpoint_resume_does_not_create_an_extra_interrupt(self):
        events = [event(0, 20), event(1, 10), event(2, 30), event(3, 30),
                  event(4, 50, stack=0x4500-9), event(5, 10), event(6, 60)]
        result = analyze_events(events, DEFINITION)
        self.assertEqual(result['repeated_breakpoint_entries'], 1)
        self.assertAlmostEqual(result['turns'][0]['interrupt_ms'], 2/BASE_HZ*1000)

    def test_wrong_saved_interrupt_frame_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'Unbalanced'):
            analyze_events([event(0, 20), event(1, 10), event(2, 10),
                            event(3, 30), event(4, 50)], DEFINITION)

    def test_selected_worker_must_match_turn_direct_page(self):
        with self.assertRaisesRegex(RuntimeError, 'ownership'):
            analyze_events([event(0, 20, dp=0x1200), event(1, 10),
                            event(2, 10)], DEFINITION)

    def test_explicit_idle_window_still_validates_the_complete_trace(self):
        events = [event(0, 20), event(1, 10), event(2, 10),
                  event(3, 20, dp=0x1200), event(100, 20), event(101, 10),
                  event(102, 60)]
        with self.assertRaisesRegex(RuntimeError, 'No complete worker turns'):
            analyze_events(events, DEFINITION, (10, 90))
        result = analyze_events(events, DEFINITION, (10, 90), allow_empty_window=True)
        self.assertEqual(result['complete_turns'], 0)
        self.assertEqual(result['observed_turn_entries'], 0)
        self.assertEqual(result['window_cpu']['charged_cpu_ms'], 0)
        self.assertEqual(result['routines'], {})
        with self.assertRaisesRegex(RuntimeError, 'Missing unique console worker'):
            analyze_events(events[3:5], DEFINITION, (10, 90), allow_empty_window=True)

    def test_caller_intervals_use_their_own_cpu_ownership(self):
        events = [event(0, 20), event(1, 10), event(2, 20, dp=0x1200),
                  event(12, 20), event(21, 10), event(22, 60)]
        result = analyze_events(events, DEFINITION, intervals=[
            dict(dp=0x1200, start=1, end=21)])
        row = result['measured_intervals'][0]
        self.assertAlmostEqual(row['charged_cpu_ms'], 10/BASE_HZ*1000)
        self.assertAlmostEqual(row['off_cpu_ms'], 10/BASE_HZ*1000)
        self.assertEqual(row['interrupt_ms'], 0)
