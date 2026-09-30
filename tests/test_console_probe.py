"""Failure controls for the hardware keyboard probe's event oracle."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_console_coexistence import validate_capture

class ConsoleProbeTests(unittest.TestCase):
    def test_event_loss_duplication_and_modifiers_fail(self):
        expected=[0x3f,0x15,0x7f,0xbf,0x1bf,0x0c,0x1c]
        validate_capture(expected,bytes(288))
        for bad in (expected[1:],expected[:3]+[0x7f]+expected[3:],
                    expected[:2]+[0x3f]+expected[3:],expected[:4]+[0x2bf]+expected[5:]):
            with self.subTest(events=bad),self.assertRaises(RuntimeError):
                validate_capture(bad,bytes(288))
        for byte in (0,3):
            state=bytearray(288);state[byte]=1
            with self.subTest(state=byte),self.assertRaises(RuntimeError):
                validate_capture(expected,state)

if __name__=='__main__':unittest.main()
