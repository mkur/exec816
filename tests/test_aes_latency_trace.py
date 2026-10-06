"""Reject incomplete observations and attribute concurrent alarms by identity."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from aes_latency_trace import analyze


def concurrent_trace():
    names = ('clock_tick', 'direct_timer_begin', 'direct_timer_end',
             'direct_deadline_low_lo', 'direct_deadline_low_hi',
             'direct_deadline_high_lo', 'direct_deadline_high_hi',
             'io_begin', 'io_request_low', 'io_request_high',
             'device_due', 'device_reply')
    marks = {name: 0x100000+i for i, name in enumerate(names)}
    events = []

    def emit(name, dp=0xa00, a=0, x=0):
        events.append((len(events)*100, ['cpu', '', '', '', hex(marks[name]),
                       hex(a), hex(x), '0', '0', hex(dp)]))

    for cohort in range(3):
        emit('clock_tick')
        for dp, pointer in ((0xb00, 0x300020), (0xc00, 0x300100)):
            emit('direct_timer_begin', dp)
            for part, value in (('low_lo', cohort*2+2), ('low_hi', 0),
                                ('high_lo', 0), ('high_hi', 0)):
                emit('direct_deadline_'+part, dp, value)
            emit('io_begin', dp, 5)
            emit('io_request_low', dp, pointer & 65535)
            emit('io_request_high', dp, pointer >> 16)
        emit('clock_tick')
        # Equal deadlines, reverse expiry order, then opposite return order.
        for pointer in (0x300100, 0x300020):
            emit('device_due')
            emit('device_reply', a=pointer & 65535, x=pointer >> 16)
        emit('direct_timer_end', 0xb00)
        emit('direct_timer_end', 0xc00)
    return events, marks


class AESLatencyTraceTests(unittest.TestCase):
    def test_equal_deadlines_keep_exact_client_and_request(self):
        events, marks = concurrent_trace()
        report = analyze(events, marks, 6)
        self.assertEqual(report['calls'], 6)
        self.assertEqual(report['expiry_count'], 6)
        self.assertEqual([alarm['client_dp'] for alarm in report['alarms']],
                         [0xc00, 0xb00]*3)
        self.assertEqual([row['alarm'] for row in report['records']],
                         [0x300020, 0x300100]*3)
        self.assertEqual(report['operations']['24']['transport'], 'direct')
        self.assertNotIn('submit_to_service', report['operations']['24'])

    def test_missing_return_is_not_zero_latency(self):
        events, marks = concurrent_trace()
        with self.assertRaisesRegex(RuntimeError, 'Uncollected AES calls'):
            analyze(events[:-1], marks, 6)

    def test_missing_deadline_is_rejected(self):
        events, marks = concurrent_trace()
        events = [(time, event) for time, event in events
                  if int(event[4], 16) != marks['direct_deadline_high_hi']]
        with self.assertRaisesRegex(RuntimeError, 'Missing caller alarm deadline'):
            analyze(events, marks, 6)
