import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from record_console_responsiveness import check_replay, visible_verdict


class ResponsivenessEvidence(unittest.TestCase):
    def test_late_first_sample_does_not_prove_a_missed_target(self):
        sample = dict(includes_caret=True, first_correct_frame_upper_ms=50,
                      last_incorrect_frame_ms=30)
        self.assertEqual(visible_verdict([sample]), 'unqualified')
        sample['last_incorrect_frame_ms'] = 41
        self.assertEqual(visible_verdict([sample]), 'fail')
        sample.update(first_correct_frame_upper_ms=40, last_incorrect_frame_ms=20)
        self.assertEqual(visible_verdict([sample]), 'pass')

    def test_glyph_only_does_not_qualify_visible_caret(self):
        with self.assertRaisesRegex(RuntimeError, 'caret'):
            visible_verdict([dict(includes_caret=False)])

    def test_replay_requires_matching_image_pixels_phase_and_no_observer(self):
        measured = dict(status='pass', observed=True, build=dict(xex_sha256='image'),
            pin='machine', screen_sha256='pixels', scanout=[dict(key='A', phase_base_cycles=0)])
        replay = copy.deepcopy(measured)
        replay['observed'] = False
        check_replay(measured, replay)
        for key, replacement, message in [('build', dict(xex_sha256='other'), 'image'),
                ('screen_sha256', 'other', 'pixels'), ('observed', True, 'observers'),
                ('scanout', [dict(key='A', phase_base_cycles=3547)], 'phases')]:
            changed = {**replay, key: replacement}
            with self.assertRaisesRegex(RuntimeError, message):
                check_replay(measured, changed)
