"""Reject malformed Exec memory ABI inputs before building target code."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_heap import ABI, CLASSIC_FLAGS, NATIVE_FLAGS, constants, generate, public_api, check_routine, declarations


class HeapPackageTests(unittest.TestCase):
    def test_classic_flags_and_native_placement_do_not_alias(self):
        self.assertFalse(set(v for v in CLASSIC_FLAGS.values() if v)&set(NATIVE_FLAGS.values()))
        c=constants()
        self.assertEqual(c['FLAG_CHIP'],2)
        self.assertEqual(c['FLAG_BANK0'],8)
        self.assertEqual(c['FLAG_NO_EXPUNGE'],0x80000000)
        self.assertEqual(c['MAX_ORDINARY'],65536)
        self.assertEqual(c['MAX_VECTOR_ORDINARY'],65528)
        self.assertEqual(c['ADDRESS_END'],0x1000000)
        self.assertNotIn('LINEAR_OWNER',c)
        self.assertNotIn('PROFILE_VERSION',c)

    def test_layouts_and_isolated_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            for count in (1,16,256):
                output=Path(directory)/str(count)
                c=generate(output,count)
                self.assertEqual(c['MEMHEADER_BYTES'],28)
                self.assertEqual(c['MEMHEADER_MH_UPPER'],20)
                self.assertEqual(c['MEMCHUNK_BYTES'],8)
                self.assertEqual(c['VECPREFIX_BYTES'],8)
                self.assertEqual(c['MAX_BANKS'],count)
                generate(output,count,check=True)
                self.assertEqual(json.loads((output/'heap.json').read_text())['abi'],ABI)
            for count in (0,257,True):
                with self.assertRaises(ValueError): constants(max_banks=count)

    def test_rejects_collisions_flags_and_layout_corruption(self):
        mutations=[lambda a:a['services'].update(ALLOC_MEM=23),
                   lambda a:a['services'].update(ALLOC_MEM=58),
                   lambda a:a['services'].update(FREE_MEM=15),
                   lambda a:a['errors'].update(CORRUPT=0xff11),
                   lambda a:a.update(owner=2),lambda a:a.update(alignment=2),
                   lambda a:a['flags'].update(CHIP=8),
                   lambda a:a['records']['MemHeader']['fields'][4].__setitem__(2,18),
                   lambda a:a['records']['MemChunk'].update(size=7),
                   lambda a:a['compiler_frame'].update(x=8)]
        for mutation in mutations:
            abi=copy.deepcopy(ABI);mutation(abi)
            with self.assertRaises(ValueError): constants(abi)

    def test_staleness_and_text_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory);generate(output)
            include=output/'heap-action.inc'
            include.write_bytes(include.read_bytes().replace(b'\n',b'\r\n'))
            generate(output,check=True)
            include.write_text(include.read_text().replace('H_ALIGNMENT=$8','H_ALIGNMENT=$2'))
            with self.assertRaisesRegex(ValueError,'Stale'): generate(output,check=True)
        self.assertIn('PUBLIC CONST MEMF_CLEAR=$10000',public_api())
        self.assertIn('PUBLIC TYPE MemHeader',public_api())
        self.assertNotIn('VecPrefix',public_api())
        self.assertNotIn(' FUNC Alloc(',declarations())

    def test_imports_reject_truncation_and_missing_padding(self):
        for name,original in ABI['imports'].items():
            shape=copy.deepcopy(original);check_routine(shape,name)
            shape['arguments'][-1]['size']-=1
            with self.assertRaisesRegex(ValueError,'call layout'): check_routine(shape,name)
            shape=copy.deepcopy(original);shape['result_bytes']+=1
            with self.assertRaisesRegex(ValueError,'result width'): check_routine(shape,name)
        self.assertEqual(ABI['imports']['Deallocate']['arguments'][2]['offset'],6)
        self.assertEqual(ABI['imports']['Deallocate']['outgoing_bytes'],11)
        shape=copy.deepcopy(ABI['imports']['AllocMem']);shape['outgoing_bytes']=8
        with self.assertRaisesRegex(ValueError,'call layout'): check_routine(shape,'AllocMem')


if __name__=='__main__': unittest.main()
