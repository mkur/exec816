import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from blitter_completion_trace import analyze_events
from test_console_turn_profile import event

MARKS = {name: dict(entry=pc) for pc, name in enumerate((
    'GemDrawingScrollStart', 'launch', 'GemDrawingScrollPoll', 'bitmap_complete',
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
