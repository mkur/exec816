"""Pre-copy attribution must preserve nesting and separate IRQ/peer time."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from mgview_pre_copy_trace import source_calls,stages,summarize
from sio_transaction_trace import BASE_HZ


class PreCopyTraceTests(unittest.TestCase):
    rows=[dict(kind=name,start=start,end=end) for name,start,end in (
        ('window_calc_slider',10,80),('wind_set',20,40),('ExecAESContext',22,25),
        ('wind_set',50,70),('_Div32',42,48))]
    timeline=Timeline([(0,24,1,False),(24,30,1,True),
                       (30,35,2,False),(35,100,1,False)],1)

    def test_caller_stages_partition_cpu_interrupts_and_other_tasks(self):
        result=stages(self.rows,self.timeline,0,100)
        self.assertEqual([r['kind'] for r in result],[
            'before_slider','slider_size_preparation','WF_VSLSIZE',
            'slider_position_preparation','WF_VSLIDE','slider_return',
            'after_slider_before_copy'])
        for key in ('elapsed_ms','charged_cpu_ms','interrupt_ms','off_cpu_ms'):
            self.assertAlmostEqual(sum(r[key] for r in result),
                                   self.timeline.measure(0,100)[key])
        size=result[2]
        self.assertAlmostEqual(size['interrupt_ms'],6*1000/BASE_HZ)
        self.assertAlmostEqual(size['off_cpu_ms'],5*1000/BASE_HZ)

    def test_exclusive_context_cost_is_not_added_twice(self):
        report=summarize(self.rows,self.timeline,20,40,
                         {'wind_set':'binding','ExecAESContext':'context'})
        self.assertAlmostEqual(report['exclusive_cpu_ms']['context'],2*1000/BASE_HZ)
        self.assertAlmostEqual(report['exclusive_cpu_ms']['binding'],7*1000/BASE_HZ)
        self.assertAlmostEqual(sum(report['exclusive_cpu_ms'].values()),
                               report['measured']['charged_cpu_ms'])
        self.assertEqual(report['routines']['ExecAESContext']['calls'],1)

    def test_missing_or_extra_setter_is_rejected(self):
        with self.assertRaises(RuntimeError):stages(self.rows[:-2],self.timeline,0,100)
        with self.assertRaises(RuntimeError):stages(self.rows+[self.rows[1]],self.timeline,0,100)

    def test_app_source_calls_match_relocation_and_caller_stack(self):
        def event(pc,stack,dp):
            row=['cpu']*10
            row[4]=format(pc,'x');row[8]=format(stack,'x');row[9]=format(dp,'x')
            return row
        events=[(0,event(0x1010,100,1)),(1,event(0x1014,100,2)),
                (2,event(0x1014,97,1)),(3,event(0x1014,100,1))]
        rows,pending=source_calls(events,{0x10:'set_shift/vs_clip/call'},0x1000,1)
        self.assertEqual(rows,[dict(kind='set_shift/vs_clip',start=0,end=3)])
        self.assertEqual(pending,[])
