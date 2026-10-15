import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_dialog_batches import merge_model, stats
from console_turn_profile import Timeline
from sio_transaction_trace import BASE_HZ


class DialogBatches(unittest.TestCase):
    units = [dict(enter=dict(start=0,end=2),leave=dict(start=8,end=10)),
             dict(enter=dict(start=14,end=16),leave=dict(start=24,end=26))]

    def test_merge_removes_only_intermediate_ownership_and_retains_traversal(self):
        result=merge_model(Timeline([(0,26,1,False)],1),self.units)
        scale=1000/BASE_HZ
        self.assertAlmostEqual(result['removed_ownership_cpu_ms'],4*scale)
        self.assertAlmostEqual(result['transaction_cpu_ms'],22*scale)
        # Original owned cores take 6+8 ticks. The merged core also holds
        # ownership across the four ticks of traversal between transactions.
        self.assertAlmostEqual(result['owned_core_cpu_ms'],18*scale)

    def test_cpu_estimate_does_not_turn_preemption_into_drawing_work(self):
        timeline=Timeline([(0,5,1,False),(5,7,2,False),(7,10,1,False),
                           (10,14,2,False),(14,26,1,False)],1)
        result=merge_model(timeline,self.units)
        scale=1000/BASE_HZ
        self.assertAlmostEqual(result['removed_ownership_cpu_ms'],4*scale)
        self.assertAlmostEqual(result['transaction_cpu_ms'],16*scale)
        self.assertAlmostEqual(result['owned_core_cpu_ms'],12*scale)

    def test_single_unit_removes_nothing_and_excludes_entry_exit_from_core(self):
        result=merge_model(Timeline([(0,26,1,False)],1),self.units[:1])
        scale=1000/BASE_HZ
        self.assertEqual(result['removed_ownership_cpu_ms'],0)
        self.assertAlmostEqual(result['transaction_cpu_ms'],10*scale)
        self.assertAlmostEqual(result['owned_core_cpu_ms'],6*scale)

    def test_distribution_keeps_slow_tail(self):
        result=stats(list(range(1,21)))
        self.assertEqual(result['p95'],19)
        self.assertEqual(result['maximum'],20)
        self.assertEqual(result['median'],10.5)


if __name__=='__main__':
    unittest.main()
