"""Mouse stage attribution separates nested policy, device, IRQ and peers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from mgview_mouse_trace import stages
from sio_transaction_trace import BASE_HZ


class MouseTraceTests(unittest.TestCase):
    rows=[dict(kind=name,start=start,end=end) for name,start,end in (
        ('AESCURSOR_CALL',10,40),('ExecAESMouseApply',50,80),
        ('GemDrawingMouseBorrow',55,70))]
    timeline=Timeline([(0,24,1,False),(24,30,1,True),
                       (30,35,2,False),(35,100,1,False)],1)

    def test_stages_partition_all_time_without_counting_device_twice(self):
        result=stages(self.rows,self.timeline,0,100)
        self.assertEqual([r['kind'] for r in result],[
            'binding_and_dispatch','cursor_policy','policy_to_device',
            'device_apply','completion_and_return'])
        for key,value in self.timeline.measure(0,100).items():
            self.assertAlmostEqual(sum(r[key] for r in result),value)
        self.assertAlmostEqual(result[1]['interrupt_ms'],6*1000/BASE_HZ)
        self.assertAlmostEqual(result[1]['off_cpu_ms'],5*1000/BASE_HZ)
        self.assertAlmostEqual(result[3]['charged_cpu_ms'],30*1000/BASE_HZ)

    def test_missing_duplicate_and_overlapping_policy_are_rejected(self):
        with self.assertRaises(RuntimeError):stages(self.rows[1:],self.timeline,0,100)
        with self.assertRaises(RuntimeError):stages(self.rows+[self.rows[0]],self.timeline,0,100)
        rows=[dict(kind='AESCURSOR_CALL',start=10,end=60),*self.rows[1:]]
        with self.assertRaises(RuntimeError):stages(rows,self.timeline,0,100)
