import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_gem_stacks import markers, summarize


class StackObserverTests(unittest.TestCase):
    def test_linked_frame_offsets_and_crlf(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'drawing').mkdir()
            (root/'c-image.json').write_text(json.dumps(dict(
                symbols={'first': 0xc1000, 'second': 0xc1020},
                segments=[dict(address=0xc1000, bytes=[0]*128, executable=True)])))
            (root/'drawing/test.lst').write_bytes(
                b'\\ 000000 .section farcode,text\r\n'
                b'\\ 000000 .public first\r\n\\ 000000 first:\r\n'
                b'\\ 000004 1b tcs\r\n'
                b'\\ 000020 .public second\r\n\\ 000020 second:\r\n'
                b'\\ 000026 1b tcs\r\n')
            points = markers(dict(image={'routines': []}, labels={}), root)
            self.assertEqual(points[0xc1027], 'second:after-tcs')
            self.assertNotIn(0xc1047, points)

    def test_physical_pools_interrupts_and_context_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'events.log'
            events = [(0xc1000, 0x3200), (0xc1001, 0x3107),
                      (0x1600, 0x3103), (0x1700, 0x30fa),
                      (0xc1000, 0x2108), (0xc1000, 0x1ff)]
            path.write_bytes(b'Unrelated bridge output\r\n'+b''.join(
                f'[SIOTXN] cpu {i} 0 8 {pc:06x} 0000 0000 0000 {s:04x} 0c00 00 04 0\r\n'.encode()
                for i, (pc, s) in enumerate(events)))
            memory = dict(task_pools=[dict(stack_base=0x3000, stack_bytes=1024)],
                          regions={'kernel-stack': [0x1ff0, 0x2410]})
            result = summarize(path, {0xc1000:'draw', 0xc1001:'draw:after-tcs',
                                     0x1600:'native_irq', 0x1700:'context_restore'}, memory)
            self.assertEqual(result['0:selected-code']['remaining_above_floor'], 8)
            self.assertEqual(result['0:interrupt-entry']['remaining_above_floor'], 4)
            self.assertEqual(result['0:context-restore']['remaining_above_floor'], -5)
            self.assertEqual(result['kernel:selected-code']['remaining_above_floor'], 9)
            self.assertEqual(len(result), 4)


if __name__ == '__main__':
    unittest.main()
