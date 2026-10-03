import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bitmap_console_performance import spans


def event(tick,pc,dp):
    return tick,['cpu','0','0','8',f'{pc:x}','0','0','0','0',f'{dp:x}']


class PerformanceSpans(unittest.TestCase):
    def test_entry_counts_do_not_require_a_unique_c_epilogue(self):
        events=[event(0,100,0x1000),event(1,200,0x1000),
                event(2,200,0x1100),event(3,101,0x1000)]
        with patch('bitmap_console_performance.read_events',return_value=events):
            rows=spans(None,{'call':dict(entry=100,returns=[101]),
                'check':dict(entry=200,returns=[],entry_only=True)})
        self.assertEqual([(r['kind'],r['dp']) for r in rows],
                         [('check',0x1000),('check',0x1100),('call',0x1000)])

    def test_preempted_library_calls_have_separate_task_domains(self):
        events=[event(0,100,0x1000),event(10,100,0x1100),
                event(20,101,0x1100),event(30,101,0x1000)]
        with patch('bitmap_console_performance.read_events',return_value=events):
            rows=spans(None,{'pending':dict(entry=100,returns=[101])})
        self.assertEqual([(r['dp'],r['start'],r['end']) for r in rows],
                         [(0x1100,10,20),(0x1000,0,30)])

    def test_unfinished_trace_is_rejected(self):
        with patch('bitmap_console_performance.read_events',return_value=[event(0,100,0x1000)]):
            with self.assertRaisesRegex(RuntimeError,'Unfinished'):
                spans(None,{'pending':dict(entry=100,returns=[101])})

    def test_same_domain_reentry_is_rejected(self):
        events=[event(0,100,0x1000),event(10,100,0x1000)]
        with patch('bitmap_console_performance.read_events',return_value=events):
            with self.assertRaisesRegex(RuntimeError,'Nested'):
                spans(None,{'pending':dict(entry=100,returns=[101])})
