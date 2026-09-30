import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from trace_command_io import call_intervals, stats, exclusion_intervals, BASE_HZ


def cpu(tick, pc, dp):
    event = ['cpu'] + ['0'] * 9
    event[4], event[9] = format(pc, 'x'), format(dp, 'x')
    return tick, event


class CommandIOTraceTests(unittest.TestCase):
    def test_pairs_suspended_calls_by_task_domain(self):
        marks = {'worker_before_wait': 100, 'worker_after_wait': 104}
        events = [cpu(1, 100, 0x1000), cpu(2, 100, 0x2000),
                  cpu(3, 104, 0x1000), cpu(5, 104, 0x2000)]
        self.assertEqual(call_intervals(events, marks), [
            dict(site='worker_before_wait', dp=0x1000, begin=1, end=3),
            dict(site='worker_before_wait', dp=0x2000, begin=2, end=5)])

    def test_keeps_nested_calls_and_ignores_incomplete_trace_edges(self):
        marks = {'worker_before_wait': 100, 'worker_after_wait': 104,
                 'wait_before_collect': 200, 'wait_after_collect': 204}
        events = [cpu(0, 104, 0x2000), cpu(1, 100, 0x1000),
                  cpu(2, 200, 0x1000), cpu(3, 204, 0x1000),
                  cpu(4, 104, 0x1000), cpu(5, 100, 0x2000)]
        self.assertEqual(call_intervals(events, marks), [
            dict(site='wait_before_collect', dp=0x1000, begin=2, end=3),
            dict(site='worker_before_wait', dp=0x1000, begin=1, end=4)])

    def test_zero_read_boundaries_have_no_invented_mean(self):
        self.assertEqual(stats([]), dict(count=0, mean_ms=None, min_ms=None,
                                         max_ms=None, sum_ms=0))

    def test_exclusion_ignores_foreign_domains_and_permit_reschedule(self):
        sites=('driver_claim','driver_activate','driver_finish','driver_stopping','io_submit')
        marks={s+suffix:100+10*i+offset for i,s in enumerate(sites)
               for suffix,offset in (('_after_tasks_forbid',0),('_before_tasks_permit',4))}
        events=[cpu(0,104,0x1000),cpu(10,100,0x1000),cpu(15,104,0x2000),
                cpu(30,104,0x1000),cpu(500,108,0x1000),cpu(600,100,0x1000)]
        result=exclusion_intervals(events,marks)
        self.assertEqual(result['driver_claim']['count'],1)
        self.assertAlmostEqual(result['driver_claim']['mean_ms'],20/BASE_HZ*1000)
        self.assertEqual(result['io_submit']['count'],0)
