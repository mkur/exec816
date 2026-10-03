import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_input_service import add_details, drains


class InputServiceProfileTests(unittest.TestCase):
    def samples(self):
        spans = []
        captures = []
        for offset in (0, 100, 200, 300):
            captures.append(offset+22)
            for kind, start, end, value in [('input', 0, 10, 0),
                    ('input', 20, 40, 0), ('key_take', 21, 25, 0), ('key_take', 26, 30, 1)]:
                spans.append(dict(kind=kind, start=start+offset, end=end+offset,
                    return_a=value, charged_cpu_ms=.05))
        return spans, captures

    def test_submillisecond_drain_can_start_before_capture(self):
        spans, captures = self.samples()
        rows = drains(spans, captures)
        self.assertEqual([r['take_results'] for r in rows], [[0, 1]]*4)
        self.assertEqual([r['service']['start'] for r in rows], [20, 120, 220, 320])

    def test_no_success_or_a_reintroduced_audit_fails(self):
        spans, captures = self.samples()
        with self.assertRaisesRegex(RuntimeError, 'No successful'):
            drains([s for s in spans if s['kind'] != 'key_take'], captures)
        spans.append(dict(kind='key_writable', start=22, end=24, charged_cpu_ms=.01))
        with self.assertRaisesRegex(RuntimeError, 'authority audit'):
            drains(spans, captures)

    def test_missing_optional_audit_symbol_is_allowed_but_public_markers_are_required(self):
        labels = dict(tasks_find_task=10, tasks_find_task_end=20)
        result = add_details(dict(spans={}), dict(key_take={}, key_pump={}), labels)
        self.assertIn('key_find_task', result['spans'])
        with self.assertRaisesRegex(RuntimeError, 'public input'):
            add_details(dict(spans={}), dict(key_pump={}), labels)
