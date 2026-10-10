import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ideplus_media import pattern_fixture,get_sector,put_sector
class Packing(unittest.TestCase):
    def test_all_modes(self):
        image,mappings=pattern_fixture()
        for mapping in mappings:
            args=[mapping[k] for k in ('start','mode','size')]
            for sector in range(4):
                expected=bytes((i^sector^mapping['unit'])&255 for i in range(mapping['size']))
                self.assertEqual(get_sector(image,*args,sector),expected)
            before=bytes(image);replacement=bytes([0x37])*mapping['size']
            put_sector(image,*args,1,replacement)
            self.assertEqual(get_sector(image,*args,1),replacement)
            self.assertEqual(get_sector(image,*args,0),get_sector(before,*args,0))
            for other in mappings:
                if other!=mapping:
                    other_args=[other[k] for k in ('start','mode','size')]
                    self.assertEqual(get_sector(image,*other_args,1),get_sector(before,*other_args,1))
    def test_even_table(self):
        image,_=pattern_fixture(even=True)
        self.assertEqual(image[2:8:2],b'APT')
        self.assertEqual(image[1:512:2],bytes(256))
if __name__=='__main__':unittest.main()
