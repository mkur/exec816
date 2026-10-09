import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_memory import layout
from generate_heap import reserve_metadata
from banked_image import manifest,validate_extents


class RegistrationMapTests(unittest.TestCase):
    def test_metadata_follows_table_and_moves_with_kernel(self):
        for count in (16,256):
            for kernel in (2,3):
                memory=layout(max_banks=count,kernel_bank=kernel,upper_table=True)
                reserve_metadata(memory)
                storage=memory['heap_storage']
                self.assertEqual(storage['BASE'],(kernel<<16)+count*4)
                self.assertEqual(storage['CAPACITY'],count-1)
                self.assertEqual(memory['profile']['code_origin'],storage['BASE']+storage['BYTES'])
                self.assertLessEqual(memory['profile']['code_origin'],(kernel+1)<<16)
                self.assertFalse(any(r['address']<65536 for r in memory['upper_reservations']))

    def test_descriptor_overlap_is_rejected(self):
        memory=layout();reserve_metadata(memory)
        with self.assertRaisesRegex(ValueError,'upper kernel reservation'):
            validate_extents([(memory['heap_storage']['BASE'],b'X',1,0,2)],memory)

    def test_metadata_is_image_owned_before_heap_starts(self):
        memory=layout(kernel_bank=3);reserve_metadata(memory)
        image=dict(entry=memory['profile']['code_origin'],zero_fill=[],segments=[dict(
            address=memory['profile']['code_origin'],bytes=[0x6b],executable=True,writable=False)])
        blob,_=manifest(image,memory)
        self.assertEqual(blob[32+3*4:32+4*4],bytes([2,0,2,0]))
        self.assertEqual(memory['abi']['owners']['HEAP'],5)
