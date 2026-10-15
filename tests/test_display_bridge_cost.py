import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from measure_display_bridge import LAYERS, METRICS, pair_costs, split_costs
from sio_transaction_trace import BASE_HZ


class DisplayBridgeCost(unittest.TestCase):
    def test_nested_subtraction_keeps_waits_and_interrupts_in_their_layer(self):
        timeline = Timeline([(0, 4, 1, False), (4, 5, 1, True),
                             (5, 10, 1, False), (10, 30, 2, False),
                             (30, 40, 1, False)], 1)
        spans = [(0, 40), (2, 38), (6, 36), (8, 34)]
        measured = [timeline.measure(*span) for span in spans]
        result = split_costs(*measured)
        scale = 1000/BASE_HZ
        self.assertAlmostEqual(result['native_ownership']['off_cpu_ms'], 20*scale)
        self.assertAlmostEqual(result['assembly_bridge']['interrupt_ms'], scale)
        for layer in LAYERS[:-1]:
            self.assertEqual(result[layer]['off_cpu_ms'], 0)
        for metric in METRICS:
            self.assertAlmostEqual(sum(result[layer][metric] for layer in LAYERS),
                                   measured[0][metric])

    def test_direct_owner_entry_has_no_action_wrapper(self):
        timeline = Timeline([(0, 20, 1, False)], 1)
        core = timeline.measure(5, 15)
        result = split_costs(timeline.measure(0, 20), timeline.measure(2, 18), core, core)
        self.assertTrue(all(value == 0 for value in result['action_wrapper'].values()))

    def test_rejects_negative_exclusive_time(self):
        timeline = Timeline([(0, 20, 1, False)], 1)
        with self.assertRaisesRegex(RuntimeError, 'not nested'):
            split_costs(timeline.measure(0, 5), timeline.measure(0, 10),
                        timeline.measure(0, 4), timeline.measure(0, 2))

    def test_pair_ignores_drawing_and_keeps_contended_pairs_separate(self):
        def row(kind, start, wait=0, signal=0):
            metrics = dict(elapsed_ms=4, charged_cpu_ms=4, off_cpu_ms=0, interrupt_ms=0)
            layers = {layer: {k: v/4 for k, v in metrics.items()} for layer in LAYERS}
            return dict(kind=kind, start=start, dp=1, status=0,
                        kernel_calls=dict(wait=wait, signal=signal), total=metrics,
                        bridge={k: v*3/4 for k, v in metrics.items()}, **layers)
        result = pair_costs([row('DisplayEnter', 0), row('DisplayLeave', 1000),
                             row('DisplayEnter', 2000, wait=1),
                             row('DisplayLeave', 3000, signal=1)])
        self.assertEqual(result['all']['count'], 2)
        self.assertEqual(result['uncontended_no_wake']['count'], 1)
        self.assertEqual(result['all']['total']['elapsed_ms']['mean'], 8)


if __name__ == '__main__':
    unittest.main()
