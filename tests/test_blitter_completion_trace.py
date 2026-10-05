import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from blitter_completion_trace import analyze_events
from test_console_turn_profile import event

MARKS = {name: dict(entry=pc) for pc, name in enumerate((
    'GemDrawingScrollStart', 'launch', 'GemDrawingPoll', 'bitmap_complete',
    'completion_blitter_irq_complete', 'completion_blitter_irq_posted',
    'completion_selected', 'completion_tasks_wait'), 10)}


class BlitterCompletionTrace(unittest.TestCase):
    def test_polling_baseline_does_not_claim_hardware_edges(self):
        r = analyze_events([event(0, 11), event(1, 10), event(2, 11),
                            event(4, 12), event(9, 12), event(10, 13)], MARKS)
        self.assertEqual(len(r['scrolls']), 1)
        row = r['scrolls'][0]
        self.assertEqual(row['polls'], 2)
        self.assertIsNone(row['hardware_busy_end'])
        self.assertIsNone(row['launch_to_irq_observation_upper_ms'])

    def test_irq_uses_saved_owner_after_interrupt_changes_dp(self):
        r = analyze_events([event(1, 10), event(2, 11), event(3, 17),
                            event(8, 14, dp=0), event(9, 15, dp=0),
                            event(10, 16, dp=0x1200), event(12, 16),
                            event(14, 12), event(16, 13)], MARKS)
        row = r['scrolls'][0]
        self.assertEqual((row['irq'], row['posted'], row['resumed']), (8, 9, 12))
        self.assertEqual((row['polls'], row['waits']), (1, 1))

    def test_incomplete_or_overlapping_scroll_fails(self):
        for events in ([event(1, 10), event(2, 11)],
                       [event(1, 10), event(2, 11), event(3, 10), event(4, 11)]):
            with self.assertRaises(RuntimeError):
                analyze_events(events, MARKS)

    def test_cpu_cost_keeps_nested_watchdog_inside_irq_total(self):
        from blitter_completion_trace import cpu_cost
        from sio_transaction_trace import BASE_HZ
        marks={name:dict(entry=pc) for name,pc in (
            ('completion_selected',20),('completion_native_irq',30),
            ('completion_native_nmi',40),('completion_interrupt_schedule',50),
            ('completion_blitter_watchdog',60),('completion_blitter_watchdog_done',70))}
        events=[event(0,20),event(3,30),event(4,60,dp=0),event(5,70,dp=0),
                event(6,50,stack=0x4500-9),event(7,20,dp=0x1200),
                event(17,20),event(20,80)]
        rows=[dict(start=0,adopt_begin=20,worker_dp=0x1100)]
        cpu_cost(events,marks,rows)
        cpu=rows[0]['cpu']
        self.assertAlmostEqual(cpu['worker_charged_ms'],7/BASE_HZ*1000)
        self.assertAlmostEqual(cpu['native_interrupt_ms'],3/BASE_HZ*1000)
        self.assertAlmostEqual(cpu['watchdog_nested_ms'],1/BASE_HZ*1000)
        self.assertAlmostEqual(cpu['worker_plus_native_interrupt_ms'],10/BASE_HZ*1000)
        self.assertEqual(cpu['watchdog_checks'],1)
        with self.assertRaises(RuntimeError):
            cpu_cost(events[:4],marks,rows)
