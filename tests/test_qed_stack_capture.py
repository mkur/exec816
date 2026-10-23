"""Interactive lifetime count is independent of the selected stack window."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from native_program import ROOT
from program_image_layout import FIELDS
from qed_stack_observer import capture


class Bridge:
    def __init__(self):
        self.ordinal = 0
        self.profiles = []
        self.fields = {name: offset for name, _, offset in
                       json.loads((ROOT/'abi/process.json').read_text())['record']}

    def bp_clear_all(self): pass
    def bp_set(self, *args, **kwargs): pass
    def regs(self): return {}
    def eval_expr(self, expression): return self.ordinal*100 if expression == '@clk' else 0
    def profile_start(self, kind): self.profiles.append(self.ordinal)
    def profile_stop(self): pass

    def memdump(self, address, size):
        data = bytearray(size)
        def put(offset, value, width):
            data[offset:offset+width] = value.to_bytes(width, 'little')
        if address == 0x10000+7*128:
            put(self.fields['state'], 1, 1)
            put(self.fields['identity'], self.ordinal, 4)
            put(self.fields['image'], 0x20000, 3)
        elif address == 0x20000:
            put(FIELDS['kind'], 1, 1)
            put(FIELDS['text'], 0x220000, 3)
            put(FIELDS['entry'], 0x220100, 3)
        return bytes(data)


class StackCapture(unittest.TestCase):
    def exercise(self, index, **options):
        bridge = Bridge(); record = {}; seen = []
        program = dict(image=dict(data=[dict(name='M_PROCESSSTATE_TABLE',
            address=0x10000, size=4+8*128)]),
            labels=dict(native_cop=10, context_restore=20))
        def run_to(b, address, **kwargs):
            if address == 10: b.ordinal += 1
        with patch('os_boundary.run_to', run_to):
            capture(bridge, program, record, index,
                    during_run=lambda owner: seen.append(owner['identity']), **options)
        return bridge, record, seen

    def test_first_stack_window_keeps_all_interactions(self):
        bridge, record, seen = self.exercise(0, observation_count=4)
        self.assertEqual(seen, [1, 2, 3, 4])
        self.assertEqual(bridge.profiles, [1])
        self.assertEqual(record['stack_window']['identity'], 1)
        self.assertNotIn('stack_windows', record)

    def test_default_last_window(self):
        bridge, record, seen = self.exercise(3)
        self.assertEqual(seen, [1, 2, 3, 4])
        self.assertEqual(bridge.profiles, [4])
        self.assertEqual(record['stack_window']['identity'], 4)

    def test_all_windows_remain_available(self):
        bridge, record, seen = self.exercise(3, profile_all=True)
        self.assertEqual(bridge.profiles, seen)
        self.assertEqual([v['identity'] for v in record['stack_windows']], seen)


if __name__ == '__main__': unittest.main()
