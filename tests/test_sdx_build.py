"""SDX phase ownership and source-to-wire admission contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import generate_memory
import task_capacity
import sdx_build
import sdx_fixtures
from sdx_file import parse,place


class SDXBuildTests(unittest.TestCase):
    def memory(self):
        memory=generate_memory.layout(upper_table=True)
        task_capacity.configure(memory,8)
        return memory

    def test_pool_has_phase_ownership_guards_and_no_task_growth(self):
        memory=self.memory()
        previous=copy.deepcopy(memory)
        with tempfile.TemporaryDirectory() as out:
            sdx_build.configure(out,memory)
        self.assertEqual(memory['phase_reservations']['loading'],previous['phase_reservations']['loading'])
        self.assertEqual(memory['task_pools'],previous['task_pools'])
        self.assertEqual(memory['bank_zero_budget']['fixed_runtime']-previous['bank_zero_budget']['fixed_runtime'],544)
        pool=memory['sdx_storage']['dp_reservation']
        self.assertEqual((pool['address']+16)%256,0)
        self.assertEqual(pool['size'],544)
        for phase in ('initialization','runtime'):
            self.assertIn(pool,memory['phase_reservations'][phase])

    def test_no_pool_fit_fails_without_overlapping_a_live_reservation(self):
        memory=self.memory()
        memory['runtime_free_ranges']=[]
        with tempfile.TemporaryDirectory() as out,self.assertRaisesRegex(ValueError,'No aligned'):
            sdx_build.configure(out,memory)

    def test_serialized_fixture_relocates_and_keeps_patch_outside_fixups(self):
        with tempfile.TemporaryDirectory() as out:
            first=sdx_fixtures.assemble(out,'process')
            second=sdx_fixtures.assemble(out,'process')
        self.assertEqual(first,second)
        program=parse(first['bytes'])
        symbols={k:v['address'] for k,v in sdx_build.ABI['guest_services'].items()}
        for base in (0x3000,0x4100):
            image,layout=place(program,base,0xe000,symbols)
            self.assertEqual(layout['exports']['MAIN'],base)
            self.assertEqual(image[base+first['patch']],0x78)
            self.assertTrue(all(first['patch'] not in (site,site+1)
                                for f in program.fixups for block,site in f.sites))

    def test_service_probe_covers_imports_and_distinguishes_pointer_classes(self):
        with tempfile.TemporaryDirectory() as out:
            item=sdx_fixtures.assemble(out,'services')
        program=parse(item['bytes'])
        md5_services={name for name,item in sdx_build.ABI['guest_services'].items()
                      if name in ('COMTAB','FILE_P') or 2<=item['event']<=13}
        self.assertEqual(set(program.imports),md5_services)
        symbols={k:v['address'] for k,v in sdx_build.ABI['guest_services'].items()}
        image,_=place(program,0x3000,0xe000,symbols)
        sites=item['direct_page_sites']
        self.assertEqual(len(sites),2)
        self.assertEqual([int.from_bytes(image[0x3000+s:0x3002+s],'little')
                          for s in sites],[0x80,0x90])
        # These argument values remain DP offsets; nearby ordinary pointers
        # are relocated into the private guest bank instead.
        self.assertTrue(all(s not in (at,at+1) for s in sites
                            for fix in program.fixups for block,at in fix.sites))


if __name__=='__main__':
    unittest.main()
