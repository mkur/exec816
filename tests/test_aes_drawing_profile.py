import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]/'tools'))
from aes_drawing_profile import partition_cpu, physical_units
from console_turn_profile import Timeline
from sio_transaction_trace import BASE_HZ


def span(kind, start, end, result=0):
    return dict(kind=kind, start=start, end=end, return_a=result)


class DrawingProfileTests(unittest.TestCase):
    def test_nested_scopes_do_not_double_charge_upload_polling_or_preemption(self):
        clock = Timeline([(0, 30, 1, False), (30, 40, 2, False),
            (40, 50, 1, False), (50, 60, 1, True), (60, 100, 1, False)], 1)
        spans = [span('objc_draw', 0, 100), span('GemDrawingBorrow', 10, 90),
            span('draw', 20, 70), span('App_just_draw', 20, 70),
            span('App_gsx_attr', 22, 26), span('GemSolidFill', 26, 65),
            span('VbxeOwnerSubmit', 28, 45), span('_VbxeUpload', 29, 31),
            span('idle', 31, 44)]
        actual = partition_cpu(clock, spans, 0, 100)
        expected = dict(aes_draw_other=20, borrow_glue=30,
            object_callback_setup=7, graphics_state=4, command_build=12,
            submission_fence=2, upload=1, completion_poll=4)
        self.assertEqual(set(actual), set(expected))
        for name, ticks in expected.items():
            self.assertAlmostEqual(actual[name], ticks/BASE_HZ*1000)
        self.assertAlmostEqual(sum(actual.values()), 80/BASE_HZ*1000)

    def test_unobserved_or_inlined_work_stays_in_its_parent_scope(self):
        clock = Timeline([(0, 100, 1, False)], 1)
        spans = [span('draw', 0, 100), span('unobserved_helper', 20, 80)]
        self.assertEqual(partition_cpu(clock, spans, 0, 100),
            dict(object_callback_setup=100/BASE_HZ*1000))

    def fixture(self):
        clock = Timeline([(0, 30, 1, False), (30, 40, 2, False),
            (40, 100, 1, False)], 1)
        drawing = span('objc_draw', 0, 100, 1)
        spans = [drawing, span('GemDrawingBorrow', 10, 90),
            span('DisplayEnter', 12, 20), span('draw', 25, 60),
            span('DisplayLeave', 75, 85)]
        return clock, drawing, spans

    def test_held_interval_excludes_admission_release_and_peer_cpu(self):
        clock, drawing, spans = self.fixture()
        unit, = physical_units(clock, spans, drawing)
        self.assertAlmostEqual(unit['owned_core']['charged_cpu_ms'], 45/BASE_HZ*1000)
        self.assertAlmostEqual(unit['owned_core']['off_cpu_ms'], 10/BASE_HZ*1000)
        self.assertAlmostEqual(unit['callback']['charged_cpu_ms'], 25/BASE_HZ*1000)
        self.assertEqual(unit['counts']['DisplayEnter'], 1)
        self.assertEqual(unit['counts']['draw'], 1)

    def test_failed_grant_cannot_be_reported_as_successful_ownership(self):
        clock, drawing, spans = self.fixture()
        spans[2]['return_a'] = 1
        with self.assertRaisesRegex(RuntimeError, 'Failed drawing ownership'):
            physical_units(clock, spans, drawing)

    def test_truncated_unit_cannot_be_accepted(self):
        clock, drawing, spans = self.fixture()
        with self.assertRaisesRegex(RuntimeError, 'Expected one DisplayLeave'):
            physical_units(clock, spans[:-1], drawing)

    def test_callback_must_execute_inside_the_grant(self):
        clock, drawing, spans = self.fixture()
        spans[3]['start'] = 15
        with self.assertRaisesRegex(RuntimeError, 'outside acquired'):
            physical_units(clock, spans, drawing)

    def test_adjacent_units_are_kept_separate(self):
        clock = Timeline([(0, 200, 1, False)], 1)
        drawing = span('objc_draw', 0, 200, 1)
        spans = [drawing]
        for offset in (0, 100):
            spans.extend([span('GemDrawingBorrow', offset+10, offset+90),
                span('DisplayEnter', offset+12, offset+20),
                span('draw', offset+25, offset+60),
                span('DisplayLeave', offset+75, offset+85)])
        self.assertEqual(len(physical_units(clock, spans, drawing)), 2)
