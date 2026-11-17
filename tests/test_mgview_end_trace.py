"""END attribution must distinguish release from wrapper return and peer IRQs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from mgview_end_trace import charged_peers,resource_stages
from sio_transaction_trace import BASE_HZ


class EndTraceTests(unittest.TestCase):
    rows=[dict(kind=name,start=start,end=end) for name,start,end in (
        ('AESLOCKS_CALL',10,90),('AESLOCKS_RELEASE',20,60),
        ('AESWINDOWSTATE_ENDUPDATE',30,50),
        ('AESLOCKS_RETURNRESOURCE',70,85),('semaphores_release',74,75))]

    def test_stages_reconcile_with_post_release_scheduling(self):
        segments=[(0,75,1,False),(75,80,2,False),(80,100,1,False)]
        timeline=Timeline(segments,1)
        stages=resource_stages(self.rows,0,100)
        self.assertEqual(sum(r['end']-r['start'] for r in stages),100)
        release=next(r for r in stages if r['kind']=='post_release_permit_and_return')
        self.assertEqual((release['start'],release['end']),(75,85))
        self.assertAlmostEqual(timeline.measure(**{k:release[k] for k in ('start','end')})['off_cpu_ms'],
                               5*1000/BASE_HZ)
        for key in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms'):
            self.assertAlmostEqual(sum(timeline.measure(r['start'],r['end'])[key] for r in stages),
                                   timeline.measure(0,100)[key])

    def test_missing_or_ambiguous_native_release_rejected(self):
        with self.assertRaises(RuntimeError):resource_stages(self.rows[:-1],0,100)
        with self.assertRaises(RuntimeError):resource_stages(self.rows+[self.rows[-1]],0,100)

    def test_peer_cpu_clipping_separates_interrupts(self):
        segments=[(0,10,1,False),(10,20,2,False),(20,25,2,True),
                  (25,30,3,False),(30,40,1,True)]
        peers=charged_peers(segments,15,35,1,{2:'SCRENMGR',3:'test controller'})
        self.assertEqual([r['role'] for r in peers],['SCRENMGR','test controller'])
        self.assertAlmostEqual(peers[0]['charged_cpu_ms'],5*1000/BASE_HZ)
        self.assertAlmostEqual(peers[0]['interrupt_ms'],5*1000/BASE_HZ)
        self.assertAlmostEqual(sum(r['charged_cpu_ms']+r['interrupt_ms'] for r in peers),
                               Timeline(segments,1).measure(15,35)['off_cpu_ms'])
