"""END attribution must distinguish release from wrapper return and peer IRQs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from console_turn_profile import Timeline
from mgview_end_trace import charged_peers,resource_stages
from measure_mgview import manager_identity
from sio_transaction_trace import BASE_HZ


class EndTraceTests(unittest.TestCase):
    def test_sleeping_manager_identity_follows_context_to_task(self):
        memory={}
        def pointer(address,value):
            memory.update({address+i:b for i,b in enumerate(value.to_bytes(3,'little'))})
        pointer(0x90000,0x100000)
        pointer(0x100000,0x110000)
        pointer(0x1300+192,0x200000)
        pointer(0x1600+192,0x210000)
        pointer(0x200000,0x120000)
        pointer(0x210000,0x110000)
        class Bridge:
            def memdump(self,address,size):
                return bytes(memory.get(address+i,0) for i in range(size))
        program=dict(image=dict(data=[dict(name='M_DESKSTATE_SERVICE_TEST',address=0x90000)]),
                     build=dict(memory=dict(task_pools=[dict(dp=0x1300),dict(dp=0x1600)])))
        self.assertEqual(manager_identity(Bridge(),program),dict(task=0x110000,dp=0x1600))

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

    def test_removed_journal_has_no_synthetic_work_stage(self):
        stages=resource_stages([r for r in self.rows if r['kind']!='AESWINDOWSTATE_ENDUPDATE'],0,100)
        self.assertNotIn('journal_and_cache',[r['kind'] for r in stages])
        self.assertEqual(sum(r['end']-r['start'] for r in stages),100)

    def test_peer_cpu_clipping_separates_interrupts(self):
        segments=[(0,10,1,False),(10,20,2,False),(20,25,2,True),
                  (25,30,3,False),(30,40,1,True)]
        peers=charged_peers(segments,15,35,1,{2:'SCRENMGR',3:'test controller'})
        self.assertEqual([r['role'] for r in peers],['SCRENMGR','test controller'])
        self.assertAlmostEqual(peers[0]['charged_cpu_ms'],5*1000/BASE_HZ)
        self.assertAlmostEqual(peers[0]['interrupt_ms'],5*1000/BASE_HZ)
        self.assertAlmostEqual(sum(r['charged_cpu_ms']+r['interrupt_ms'] for r in peers),
                               Timeline(segments,1).measure(15,35)['off_cpu_ms'])
