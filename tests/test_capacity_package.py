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
        self.assertEqual(m['bank_zero_budget']['runtime_excluding_os'],22336)
        self.assertEqual(m['bank_zero_budget']['loading_excluding_os'],21872)
        self.assertTrue(all(p['dp_reserved_bytes']==256 for p in pools))

    def test_compact_maps_preserve_all_stack_reservations(self):
        for capacity,bases,total,loading in (
            (4,[0x4200,0x5200,0x6900,0x7100,0x7900],51632,54368),
            (8,[0x4200,0x5200,0x6810,0x6c30,0x7050,0x7470,0x7890,0x0d20,0x7cb0],53056,52592)):
            with self.subTest(capacity=capacity):
                m=layout(upper_table=capacity==8)
                pools=configure(m,capacity)
                self.assertEqual(m['regions']['kernel-dp'],[0x2100,0x2200])
                self.assertEqual([p['dp'] for p in pools],[0x2200+i*256 for i in range(capacity+1)])
                self.assertEqual([p['stack_base'] for p in pools],bases)
                self.assertTrue(all(p['dp_reserved_bytes']==256 for p in pools))
                budget=m['bank_zero_budget']
                self.assertEqual(budget['runtime_including_os'],total)
                self.assertEqual(budget['loading_including_os'],loading)
                self.assertEqual(sum(r['size'] for r in m['runtime_reservations']),total)
                self.assertEqual(m['regions']['kernel-stack'],[0x49f0,0x5010])

    def test_dp_alignment_ownership_and_reserved_capacity(self):
        for key,value in (('task_base',0x2201),('task_stride',512),('kernel',0x2101)):
            m=layout(upper_table=True)
            m['profile']['direct_pages'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                configure(m,8)
        for capacity,base in ((4,0x2400),(8,0x2500),(8,0x2100),(8,0xff00)):
            m=layout(upper_table=capacity==8)
            m['profile']['direct_pages']['task_base']=base
            with self.subTest(capacity=capacity,base=base),self.assertRaisesRegex(RuntimeError,'overlaps'):
                configure(m,capacity)
        # The unused portion of the near bank table remains reserved too.
        m=layout()
        m['regions']['foreign']=[0x2bf0,0x2c00]
        with self.assertRaisesRegex(RuntimeError,'overlaps'):
            configure(m,4)
        m=layout(upper_table=True)
        m['profile']['task_stacks']['8']['bases'][3]=0x6800
        with self.assertRaisesRegex(RuntimeError,'overlaps'):
            configure(m,8)

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
