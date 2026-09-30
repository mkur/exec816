"""A sampled PC16 must not falsely complete an upper-bank target execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from os_boundary import run_to


class SampledBridge:
    def __init__(self, complete=True):
        self.complete = complete
        self.samples = 0
        self.pauses = 0

    def eval_expr(self, expression):
        if expression == '@frame':
            return self.samples
        assert expression == 'dw($2000)!=$ffff'
        return int(self.complete and self.samples >= 2)

    def regs(self):
        self.samples += 1
        # First sample is an upper-bank instruction whose low PC equals done.
        return {'PC':'$3d61', 'sample':self.samples}

    def resume(self):
        pass

    def pause(self):
        self.pauses += 1


class RendezvousTests(unittest.TestCase):
    @patch('os_boundary.time.sleep')
    def test_completion_rejects_matching_pc_before_publication(self, _sleep):
        bridge = SampledBridge()
        regs = run_to(bridge,0x3d61,condition='dw($2000)!=$ffff')
        self.assertEqual(regs['sample'],2)
        self.assertEqual(bridge.pauses,1)

    @patch('os_boundary.time.sleep')
    def test_unqualified_pc_still_obeys_frame_bound(self, _sleep):
        bridge = SampledBridge(complete=False)
        with self.assertRaisesRegex(RuntimeError,'within 2 frames'):
            run_to(bridge,0x3d61,frame_limit=2,condition='dw($2000)!=$ffff')
        self.assertEqual(bridge.samples,3)
        self.assertEqual(bridge.pauses,1)
