"""Reject incompatible signal layouts, widths and metadata placement."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_tasks import ABI, constants, check_routine, generate, storage
from generate_memory import layout
from banked_image import validate_extents


class SignalsPackageTests(unittest.TestCase):
    def test_task_layout_rejects_overlapping_fields(self):
        self.assertEqual(constants()['TASK_SIZE'],62)
        bad = copy.deepcopy(ABI); bad['task']['fields'][-1][2]=57
        with self.assertRaisesRegex(RuntimeError,'layout'):
            constants(bad)

    def test_full_masks_and_native_padding_are_required(self):
        for name in ('Wait','SetSignal','Signal'):
            expected = copy.deepcopy(ABI['imports'][name])
            check_routine(expected,name)
            expected['arguments'][-1]['size']=3
            with self.assertRaisesRegex(RuntimeError,'arguments'):
                check_routine(expected,name)
        wrong = copy.deepcopy(ABI['imports']['Wait']); wrong['result_bytes']=3
        with self.assertRaisesRegex(RuntimeError,'result'):
            check_routine(wrong,'Wait')
        wrong = copy.deepcopy(ABI['imports']['Signal']); wrong['arguments'][1]['offset']=3
        with self.assertRaisesRegex(RuntimeError,'arguments'):
            check_routine(wrong,'Signal')

    def test_selectors_cannot_collide(self):
        for selector, message in [(15,'collision'),(17,'Duplicate')]:
            bad = copy.deepcopy(ABI); bad['services']['WAIT']=selector
            with self.assertRaisesRegex(RuntimeError,message): constants(bad)

    def test_metadata_tracks_actual_upper_memory_and_cannot_overlap_image(self):
        memory = layout(); c=storage(memory)
        self.assertEqual(c['BASE'],0xf0000)
        self.assertEqual(c['METADATA_BYTES'],704)
        self.assertEqual(c['WAKE'],c['BASE']+5*64+9)
        smaller = copy.deepcopy(memory); smaller['usable_banks']=[2,3]
        self.assertEqual(storage(smaller)['BASE'],0x30000)
        empty = copy.deepcopy(memory); empty['usable_banks']=[]
        with self.assertRaisesRegex(RuntimeError,'upper'): storage(empty)
        with self.assertRaisesRegex(ValueError,'overlap'):
            validate_extents([(c['BASE'],b'',c['METADATA_BYTES'],1,2),
                              (c['BASE']+2,b'\x6b',1,2,2)],memory)
        with tempfile.TemporaryDirectory() as temp:
            generate(Path(temp),memory)
            assembly=(Path(temp)/'task-abi.inc').read_text()
            self.assertIn('T_BASE = $0f0000',assembly)
            self.assertIn('T_TCB_WAKENODE = $000020',assembly)
