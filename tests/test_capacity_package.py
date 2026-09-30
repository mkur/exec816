import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_memory import layout
from task_capacity import configure
from banked_image import validate_extents, manifest
from generate_tasks import storage


class CapacityPackaging(unittest.TestCase):
    def test_kernel_parameter_and_table(self):
        for bank in (1,3):
            m=layout(kernel_bank=bank,upper_table=True)
            self.assertEqual(m['constants']['TABLE'],bank<<16)
            self.assertEqual(m['profile']['code_origin'],(bank<<16)+64)
            self.assertNotIn('table',m['regions'])
            with self.assertRaises(ValueError):
                validate_extents([(bank<<16,b'x',1,0,2)],m)
        for bank in (0,16,256,-1,True):
            with self.assertRaises(ValueError):layout(kernel_bank=bank)
        with self.assertRaises(ValueError):layout(max_banks=3,kernel_bank=3)

    def test_table_bank_stays_reserved_without_code(self):
        memory=layout(kernel_bank=3,upper_table=True)
        image=dict(entry=0x40000,zero_fill=[],segments=[dict(address=0x40000,bytes=[0x6b],executable=True)])
        blob,_=manifest(image,memory)
        self.assertEqual(blob[32+3*4:32+4*4],bytes([2,0,2,0]))
        with self.assertRaises(ValueError):
            validate_extents([(0x30040,b'x',1,0,3)],memory)

    def test_eight_pool_reservations(self):
        m=layout(upper_table=True)
        pools=configure(m,8)
        self.assertEqual(len(pools),9)
        self.assertEqual([p['stack_bytes'] for p in pools],[1536]+[1024]*7+[512])
        self.assertTrue(all(p['dp']%256==0 for p in pools))
        spans=m['runtime_reservations']
        self.assertTrue(all(a['address']+a['size']<=b['address'] for a,b in zip(spans,spans[1:])))
        c=storage(m)
        self.assertEqual((c['CAPACITY'],c['IDLE'],c['PUBLIC_CONTEXT_BYTES'],c['METADATA_BYTES']),(8,8,512,1216))
        self.assertEqual(m['bank_zero_budget']['runtime_excluding_os'],24672)
        self.assertEqual(m['bank_zero_budget']['loading_excluding_os'],20368)
        self.assertTrue(all(p['dp_reserved_bytes']==512 for p in pools))

    def test_invalid_or_oversized_pools(self):
        for capacity in (0,1,17,True):
            with self.assertRaises(RuntimeError):configure(layout(upper_table=True),capacity)
        for size in (256,513,2048,True):
            with self.assertRaises(RuntimeError):configure(layout(upper_table=True),8,size)
        with self.assertRaises((ValueError,RuntimeError)):
            configure(layout(upper_table=True),16,1536,1536)
        with self.assertRaises(RuntimeError):configure(layout(),8)

    def test_full_bank_table_size(self):
        m=layout(max_banks=256,kernel_bank=3,upper_table=True)
        self.assertEqual(m['constants']['TABLE_BYTES'],1024)
        self.assertEqual(m['profile']['code_origin'],0x30400)
        with self.assertRaises(ValueError):
            validate_extents([(0x303ff,b'xx',2,2,2)],m)


if __name__=='__main__':unittest.main()
