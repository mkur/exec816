"""Failure controls for the shared-clock observer, including CRLF input."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mouse_timer_trace import accounting


class MouseTimerTraceTests(unittest.TestCase):
    labels = dict(timer_tick=0x1234, sio_alarm=0x2345, timer_sample=0x3456)

    def observe(self, fault=None):
        rows = ['[SIOTXN] timer 100 0', '[SIOTXN] register 101 14 0']
        entries = [0x1234, 0x2345, 0x3456]
        if fault == 'backend':
            entries.append(0x3456)
        if fault == 'dispatch':
            entries.append(0x1234)
        if fault == 'unacknowledged':
            rows.pop()
        rows += [f'[SIOPOC] cpu {102+i} 0 8 {pc:06x} 0 0 0 0 0 0 04 0'
                 for i, pc in enumerate(entries)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'trace.log'
            path.write_bytes(('unrelated chatter\r\n'+'\r\n'.join(rows)+'\r\n').encode())
            return accounting(path, self.labels)

    def test_single_dispatch(self):
        result = self.observe()
        self.assertEqual(result['physical_edges'], 1)
        self.assertEqual(result['logical_dispatches'], 1)
        self.assertEqual(result['pointer_samples'], 1)

    def test_duplicate_service_rejected(self):
        for fault in ('backend', 'dispatch'):
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                self.observe(fault)

    def test_missing_acknowledgement_rejected(self):
        with self.assertRaises(RuntimeError):
            self.observe('unacknowledged')
