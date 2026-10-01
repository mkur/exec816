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
            (4,[0x2410,0x3050,0x3670,0x3c90,0x42b0],51392,54128),
            (8,[0x2410,0x3050,0x3470,0x3890,0x3cb0,0x40d0,0x44f0,0x4910,0x4d30],53056,52592)):
            with self.subTest(capacity=capacity):
                m=layout(upper_table=capacity==8)
                pools=configure(m,capacity)
                self.assertEqual(m['regions']['kernel-dp'],[0x0a00,0x0b00])
                self.assertEqual([p['dp'] for p in pools],[0x0b00+i*256 for i in range(capacity+1)])
                self.assertEqual([p['stack_base'] for p in pools],bases)
                self.assertTrue(all(p['dp_reserved_bytes']==256 for p in pools))
                budget=m['bank_zero_budget']
                self.assertEqual(budget['runtime_including_os'],total)
                self.assertEqual(budget['loading_including_os'],loading)
                self.assertEqual(sum(r['size'] for r in m['runtime_reservations']),total)
                self.assertEqual(m['regions']['kernel-stack'],[0x2a20,0x3040])
                end = 0x48c0 if capacity == 4 else 0x4f40
                self.assertEqual(m['runtime_free_ranges'],[dict(address=end,size=0x8000-end)])
                phases=m['phase_reservations']
                self.assertEqual(sum(r['size'] for r in phases['loading']),loading)
                self.assertEqual(sum(r['size'] for r in phases['initialization']),total+2048)
                self.assertEqual([r['name'] for r in phases['initialization'] if r['name'] in ('loader','staging')],[])
                # Even the union of future pools and temporary loading bytes fits.
                combined=sorted(m['runtime_reservations']+[
                    dict(name=n,address=m['regions'][n][0],size=m['regions'][n][1]-m['regions'][n][0])
                    for n in ('loader','staging','manifest')],key=lambda r:r['address'])
                self.assertTrue(all(a['address']+a['size'] <= b['address'] for a,b in zip(combined,combined[1:])))

    def test_diagnostics_do_not_borrow_live_storage(self):
        from generate_memory import reservation_maps
        m=layout(upper_table=True)
        configure(m,8)
        for phase in m['phase_reservations'].values():
            for scratch in m['diagnostic_scratch']:
                self.assertTrue(all(scratch['address']+scratch['size'] <= r['address'] or
                                    scratch['address'] >= r['address']+r['size'] for r in phase))
        m['profile']['test_scratch'][0]['address']=0x2000
        with self.assertRaisesRegex(ValueError,'scratch overlaps live'):
            reservation_maps(m,**m['phase_reservations'])

    def test_dp_alignment_ownership_and_reserved_capacity(self):
        for key,value in (('task_base',0x2201),('task_stride',512),('kernel',0x2101)):
            m=layout(upper_table=True)
            m['profile']['direct_pages'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                configure(m,8)
        for capacity,base in ((4,0x0d00),(8,0x0e00),(8,0x0a00),(8,0xff00)):
            m=layout(upper_table=capacity==8)
            m['profile']['direct_pages']['task_base']=base
            with self.subTest(capacity=capacity,base=base),self.assertRaisesRegex(RuntimeError,'overlaps'):
                configure(m,capacity)
        # The unused portion of the near bank table remains reserved too.
        m=layout()
        m['regions']['foreign']=[0x13f0,0x1400]
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
