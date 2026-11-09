"""The public runtime manifest and generated consumers share one layout."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_c_runtime import ABI,files
from c_runtime_build import prepare,SOURCES


class RuntimeContract(unittest.TestCase):
    def test_generated_consumers_are_current(self):
        for path,content in files().items():
            self.assertEqual(path.read_text(),content,str(path.relative_to(ROOT)))

    def test_records_have_complete_nonoverlapping_extents(self):
        widths={'UWORD':2,'ULONG':4,'LONG':4,'APTR':4,'CONST_STRPTR':4}
        for name,record in ABI['records'].items():
            covered=set()
            for field,kind,offset in record['fields']:
                extent=set(range(offset,offset+widths[kind]))
                self.assertFalse(covered&extent,(name,field))
                covered|=extent
            self.assertEqual(covered,set(range(record['bytes'])),name)

    def test_bank_and_alignment_contract(self):
        limits=ABI['limits']
        self.assertEqual(limits['ALLOCATION_PREFIX']%limits['ALIGNMENT'],0)
        self.assertEqual(limits['ALLOCATION_PREFIX']+limits['MAX_ALLOCATION'],65536)
        self.assertEqual(len(set(ABI['phases'].values())),4)

    def test_typed_main_adapter_and_single_common_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            for signature,call in [('void','return main();'),('args','return main(argc,argv);')]:
                sources,record=prepare(output,[],signature)
                self.assertEqual(sources[:-1],list(SOURCES))
                self.assertIn(call,(output/'runtime-main.c').read_text())
                self.assertEqual(record['entry'],ABI['entry'])
            with self.assertRaisesRegex(RuntimeError,'Duplicate'):
                prepare(output,[SOURCES[0]])
            with self.assertRaisesRegex(RuntimeError,'Choose main'):
                prepare(output,[],'untyped')


if __name__=='__main__':unittest.main()
