"""A late refill must remain visible even when it idles the TX shifter."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from sio_adapter_trace import analyze

def trace(gap=False):
    def event(t,name,*fields):return t,[name,str(t),*map(str,fields)]
    rows=[event(0,'mask',0,8,'0','24',0,'0','78',0,0),event(1,'cpu',0,8,'1'),event(100,'command',1)]
    values=[49,82,1,0,132];ready=[2008,2148,2288,2428,2568];writes=[2000,2050,2190,2330,2470]
    if gap:
        rows.append(event(2148,'idle'));writes[1]=2148
        for i in range(1,5):ready[i]+=14
        for i in range(2,5):writes[i]+=14
    for t,v in zip(writes,values):rows.append(event(t,'write',v,255,0))
    for t,v in zip(ready,values):rows.append(event(t,'ready',v,14,16))
    rows.extend([event(ready[-1]+140,'idle'),event(4000,'command',0),event(4500,'cpu',0,8,'2'),event(4501,'mask',0,8,'0','20',0,'0','58',0,0)])
    return sorted(rows,key=lambda r:r[0])

class CommandTraceTests(unittest.TestCase):
    def test_complete_command_is_one_frame(self):
        r=analyze(None,dict(sio_start=1,sio_shutdown=2),all_events=trace())
        self.assertEqual(r['verdict'],'pass');self.assertEqual(r['tx_frames'],[[49,82,1,0,132]])
        self.assertEqual(r['tx_refill']['count'],4)
    def test_idle_edge_does_not_hide_a_late_pair(self):
        r=analyze(None,dict(sio_start=1,sio_shutdown=2),all_events=trace(True))
        self.assertEqual(r['tx_frames'],[[49,82,1,0,132]])
        self.assertEqual(r['tx_refill']['count'],4)
        self.assertIn('TX gap',r['violations']);self.assertIn('late TX refill',r['violations'])
        self.assertGreaterEqual(r['tx_refill']['max_us'],r['byte_deadline_us'])

if __name__=='__main__':unittest.main()
