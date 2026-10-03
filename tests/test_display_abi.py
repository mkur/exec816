"""Shared display ABI freshness and complete physical extent accounting."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_display import files
from generate_bitmap import files as bitmap_files
from generate_tasks import application_entry


class DisplayABI(unittest.TestCase):
    def test_generated_bindings(self):
        for path,content in (files() | bitmap_files()).items():
            with self.subTest(path=path):
                self.assertEqual(path.read_text(),content)

    def test_library_leaves_are_not_task_entries(self):
        for name in ('DISPLAY_RELEASE','DISPLAYBOOT_AUTHORIZE','DISPLAYADAPTER_RESETREQUIRED'):
            self.assertFalse(application_entry({'name':'M_'+name+'_1234'}))

    def test_vram_capacity_and_padding(self):
        memory=json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text())
        regions=sorted(memory['regions'],key=lambda r:r['base'])
        self.assertEqual(sum(r['reserved_bytes'] for r in regions),memory['reserved_bytes'])
        self.assertEqual(memory['reserved_bytes']+memory['unassigned_bytes'],memory['bytes'])
        for region in regions:
            self.assertLessEqual(region['g3_used_bytes'],region['capacity_bytes'])
            self.assertLessEqual(region['capacity_bytes'],region['reserved_bytes'])
            self.assertLessEqual(region['base']+region['reserved_bytes'],memory['bytes'])
        for left,right in zip(regions,regions[1:]):
            self.assertLessEqual(left['base']+left['reserved_bytes'],right['base'])
        bcb=next(r for r in regions if r['name']=='bcb')
        self.assertEqual(bcb['capacity_bytes'],195*21)
        self.assertEqual(bcb['base']+bcb['reserved_bytes'],0x39000)
        for diagnostic in memory['diagnostics']:
            self.assertTrue(all(diagnostic['base']+diagnostic['bytes']<=r['base'] or
                                diagnostic['base']>=r['base']+r['reserved_bytes'] for r in regions))


if __name__=='__main__':
    unittest.main()
