import unittest

from test_signal_concurrency import public_call_latencies
from sio_latency import BASE_HZ


class PublicCallTimingTests(unittest.TestCase):
    markers = dict(tasks_forbid=10, tasks_forbid_return=11,
                   tasks_permit=20, tasks_permit_return=21,
                   ports_get_msg=30, ports_get_msg_return=31)

    @staticmethod
    def event(tick, pc, stack):
        return tick, ['cpu', str(tick), '0', '8', f'{pc:x}', '0', '0', '0', f'{stack:x}']

    def test_suspended_call_is_paired_with_its_own_stack(self):
        events = [self.event(1, 30, 100), self.event(2, 30, 200),
                  self.event(3, 31, 200), self.event(9, 31, 100)]
        result = public_call_latencies(events, self.markers, 0, 20)['ports_get_msg']
        self.assertEqual(result['count'], 2)
        self.assertAlmostEqual(result['min_us'], 1.75/BASE_HZ*1e6)
        self.assertAlmostEqual(result['max_us'], 8.75/BASE_HZ*1e6)

    def test_calls_crossing_either_measurement_edge_are_excluded(self):
        events = [self.event(0, 10, 100), self.event(2, 11, 100),
                  self.event(3, 10, 100), self.event(4, 11, 100),
                  self.event(5, 10, 100), self.event(9, 11, 100)]
        result = public_call_latencies(events, self.markers, 1, 9)['tasks_forbid']
        self.assertEqual(result['count'], 1)  # final RTL would extend past tick 9


if __name__ == '__main__':
    unittest.main()
