"""Failure controls for the shared-clock observer, including CRLF input."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mouse_timer_trace import accounting
from console_concurrent_trace import shared_alarm_observations


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

    def test_armed_alarm_uses_acknowledged_edge(self):
        cpu = lambda pc: ['cpu','0','0','8',f'{pc:06x}']
        events = [(100,['timer','100','0']), (101,['register','101','14','0']),
                  (110,cpu(0x1234)), (115,['timer','115','0']), (120,cpu(0x2345))]
        self.assertEqual(shared_alarm_observations(events,self.labels),[20])

    def test_pointer_only_tick_is_not_an_armed_alarm(self):
        events = [(100,['timer','100','0']), (101,['register','101','14','0']),
                  (400,['cpu','0','0','8','001234']),
                  (410,['cpu','0','0','8','003456'])]
        self.assertEqual(shared_alarm_observations(events,self.labels),[])

    def test_alarm_without_dispatch_rejected(self):
        with self.assertRaises(ValueError):
            shared_alarm_observations([(120,['cpu','0','0','8','002345'])],self.labels)
