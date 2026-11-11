import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_program import place_after_foreign

class ForeignPlacement(unittest.TestCase):
    def test_code_cannot_grow_into_fixed_c_banks(self):
        memory={'profile':{'code_origin':0x13000,'data_origin':0x12000},'usable_banks':list(range(1,64))}
        foreign={'segments':[{'address':0xc0000,'bytes':bytes(256)}],
                 'zero_fill':[{'address':0xd0000,'size':4096}]}
        place_after_foreign(memory,foreign)
        self.assertEqual(memory['profile'],{'code_origin':0xe0000,'data_origin':0x12000})
        self.assertEqual(memory['foreign_code_placement']['foreign_end'],0xd1000)

    def test_no_available_bank_rejected(self):
        memory={'profile':{'code_origin':0x13000},'usable_banks':list(range(1,14))}
        with self.assertRaisesRegex(RuntimeError,'No native code bank'):
            place_after_foreign(memory,{'segments':[],'zero_fill':[{'address':0xd0000,'size':65536}]})

    def test_tables_reserve_the_whole_bank_before_native_code(self):
        memory={'profile':{'code_origin':0x13000},'usable_banks':list(range(1,64))}
        foreign={'segments':[{'address':0xf0000,'bytes':bytes(35082)}], 'zero_fill':[]}
        place_after_foreign(memory,foreign)
        self.assertEqual(memory['profile']['code_origin'],0x100000)

    def test_sdx_resident_bank_stays_clear_as_native_code_grows(self):
        memory={'profile':{'code_origin':0x13000,'data_origin':0x12000},
                'usable_banks':list(range(1,64)),
                'sdx_storage':{'resident_base':0x280000,'resident_reserved_bytes':65536}}
        foreign={'segments':[{'address':0x120000,'bytes':bytes(256)}], 'zero_fill':[]}
        place_after_foreign(memory,foreign)
        self.assertEqual(memory['profile'],{'code_origin':0x290000,'data_origin':0x12000})
        self.assertEqual(memory['foreign_code_placement']['fixed_image_end'],0x290000)

    def test_sdx_without_a_foreign_image_also_reserves_its_bank(self):
        memory={'profile':{'code_origin':0x13000},'usable_banks':list(range(1,64)),
                'sdx_storage':{'resident_base':0x280000,'resident_reserved_bytes':65536}}
        place_after_foreign(memory,None)
        self.assertEqual(memory['profile']['code_origin'],0x290000)
