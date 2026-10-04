"""Failure controls for the shared-clock observer, including CRLF input."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from mouse_timer_trace import accounting, cadence, require_normal_cadence
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

    def test_window_keeps_preceding_physical_edge(self):
        cpu = lambda pc: ['cpu','0','0','8',f'{pc:06x}']
        events = [(100,['timer','100','0']), (110,['register','110','14','0']),
                  (120,cpu(0x1234)), (130,cpu(0x2345))]
        self.assertEqual(shared_alarm_observations(events,self.labels,105,140),[30])
        self.assertEqual(shared_alarm_observations(events,self.labels,105,125),[])

    def test_physical_rate_and_capture_division_are_distinct(self):
        events = []
        def register(t, divisor):
            events.append((t, ['register', str(t), '0', str(divisor)]))
        def edge(t, sample=True):
            events.append((t, ['timer', str(t), '0']))
            if sample:
                events.append((t+20, ['cpu', str(t+20), '0', '8', '003456']))
        register(0, 15)
        for t in (400, 848, 1296, 1744):
            edge(t)
        register(1800, 7)
        # First interval straddles the reload change. Steady fine periods are
        # 224 cycles, but actual captures remain 448 cycles apart.
        for i, t in enumerate((2100, 2324, 2548, 2772, 2996)):
            edge(t, i % 2 == 0)
        result = cadence(events, self.labels)['au_df1']
        self.assertEqual(result['15']['median_physical_period_cycles'], 448)
        self.assertEqual(result['7']['median_physical_period_cycles'], 224)
        self.assertEqual(result['15']['pointer_samples'], 4)
        self.assertEqual(result['7']['physical_edges'], 5)
        self.assertEqual(result['7']['pointer_samples'], 3)
        self.assertAlmostEqual(result['7']['sample_period']['mean_us'],
                               result['15']['sample_period']['mean_us'])

    def test_decimation_alone_does_not_satisfy_normal_rate(self):
        observation = dict(cadence=dict(au_df1={'15': dict(physical_edges=200,
                                                   median_physical_period_cycles=224)}))
        with self.assertRaisesRegex(RuntimeError, 'physically run'):
            require_normal_cadence(observation)
