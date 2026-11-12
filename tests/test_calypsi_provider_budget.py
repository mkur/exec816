import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from calypsi_provider_budget import budget


class ProviderBudget(unittest.TestCase):
    def image(self):
        return dict(segments=[dict(address=at,bytes=[0]*size,executable=True,writable=False)
            for at,size in ((0xc0000,65536),(0xe0000,65536),(0xf0000,65536),(0x100000,18000))]+
            [dict(address=0xd0000,bytes=[0]*5000,executable=False,writable=True),
             dict(address=0x110000,bytes=[0]*100000,executable=False,writable=False)],
            zero_fill=[dict(address=0xd2000,size=18000)])

    def test_existing_shared_banks_are_counted_once(self):
        r=budget(self.image(),dict(code_bytes=8192,table_bytes=4096,data_bss_bytes=16384))
        self.assertEqual(r['readonly_capacity'],262144)
        self.assertEqual(r['readonly_bytes'],214608)
        self.assertEqual(r['mutable_bytes'],23000)

    def test_allowances_still_reject_excess(self):
        with self.assertRaisesRegex(RuntimeError,'allowances'):
            budget(self.image(),dict(code_bytes=50000,table_bytes=4096,data_bss_bytes=0))

    def test_executable_boot_asset_is_not_ignored(self):
        image=self.image();image['segments'][-1]['executable']=True
        with self.assertRaisesRegex(RuntimeError,'outside'):
            budget(image,dict(code_bytes=0,table_bytes=0,data_bss_bytes=0))

    def test_zero_fill_cannot_leave_data_bank(self):
        image=self.image();image['zero_fill'][0]['size']=65536
        with self.assertRaisesRegex(RuntimeError,'zero fill'):
            budget(image,dict(code_bytes=0,table_bytes=0,data_bss_bytes=0))
