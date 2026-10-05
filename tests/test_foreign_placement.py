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
