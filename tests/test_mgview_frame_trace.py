"""Conserve CPU attribution across nested frame spans, preemption and IRQs."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from mgview_frame_trace import partition,analyze
from sio_transaction_trace import BASE_HZ


class FrameTraceTests(unittest.TestCase):
    def test_nested_cpu_excludes_peer_and_interrupt_time(self):
        timeline=Timeline([(0,20,1,False),(20,30,2,False),
                           (30,40,1,True),(40,100,1,False)],1)
        rows=[dict(kind='paint',start=0,end=100),
              dict(kind='clear',start=10,end=50),
              dict(kind='fill',start=20,end=45)]
        costs=partition(rows,timeline,0,100,
                        dict(paint='native',clear='clear',fill='fill'))
        for name,ticks in [('native',60),('clear',15),('fill',5)]:
            self.assertAlmostEqual(costs[name],ticks*1000/BASE_HZ)
        self.assertAlmostEqual(sum(costs.values()),80*1000/BASE_HZ)

    def test_frame_stages_keep_clear_and_selected_objects_distinct(self):
        timeline=Timeline([(0,100,1,False)],1)
        def span(name,start,end,argument=0):
            return dict(kind=name,start=start,end=end,argument=argument,
                        **timeline.measure(start,end))
        rows=[span('AESFRAME_PAINT',0,100),span('widget_batch',10,90),
              span('fragment',20,70),span('fill',21,25),
              span('App_everyobj',26,65),span('frame_object',30,40,9),
              span('frame_object',45,60,10),span('VbxeOwnerSubmit',75,80,24)]
        result=analyze(rows,timeline)[0]
        self.assertEqual(result['callbacks'][0]['object_ids'],[9,10])
        self.assertEqual(len(result['callbacks'][0]['clears']),1)
        self.assertEqual(result['raw_submission_record_counts'],[24])
        self.assertEqual([(s['kind'],s['end']-s['start']) for s in result['stages']],
                         [('scratch_setup',10),('scratch_callback',50),
                          ('scratch_publication_and_fence',20)])
        self.assertAlmostEqual(sum(result['exclusive_cpu_ms'].values()),
                               result['measured']['charged_cpu_ms'])
