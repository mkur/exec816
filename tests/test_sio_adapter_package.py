"""Independent failure controls for Task-adapter timing and shared layout."""
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_sio_adapter import ABI,ROOT,assembly
from sio_adapter_trace import analyze
from test_sio_package import wire_trace,LABELS

class SioAdapterTests(unittest.TestCase):
    def test_generated_descriptor_and_extents(self):
        self.assertEqual((ROOT/'platform/altirraos/sio-state.inc').read_text(),assembly())
        self.assertLessEqual(ABI['state_offset']+ABI['state_bytes'],ABI['native_offset'])
        self.assertLessEqual(ABI['native_offset']+ABI['native_reserved_bytes'],65536)
        self.assertEqual(ABI['fields']['SD_DATA'],16)
        self.assertEqual(ABI['fields']['SD_COMMAND'],48)

    def test_wire_deadlines_have_failing_controls(self):
        for fault,expected in ((None,None),('rx','late RX read'),('tx','late TX refill'),('phase','COMMAND hold deadline')):
            rows=wire_trace()
            if fault=='rx':next(r for r in rows if r[0]=='read')[1]='4325'
            if fault=='tx':[r for r in rows if r[0]=='write'][1][1]='2050'
            if fault=='phase':[r for r in rows if r[0]=='command'][1][1]='4290'
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'trace.log'
                path.write_bytes(('unrelated private chatter\r\n'+''.join('[SIOTXN] '+' '.join(r)+'\r\n' for r in sorted(rows,key=lambda r:int(r[1])))).encode())
                result=analyze(path,dict(sio_start=LABELS['stream_start'],sio_shutdown=LABELS['critic_leave']))
            with self.subTest(fault=fault):
                self.assertEqual(result['verdict'],'pass' if fault is None else 'fail')
                if expected:self.assertIn(expected,result['violations'])
