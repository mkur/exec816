"""Observers follow native Image field alignment rather than fixed old offsets."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_program import ROOT
from program_image_layout import layout

class ImageObserverLayoutTests(unittest.TestCase):
    def test_current_requirement_field_preserves_byte_and_long_alignment(self):
        current=layout()
        self.assertEqual(current['size'],76)
        self.assertEqual({n:current['fields'][n]['offset'] for n in
            ['kind','minimumStack','data','bss','textBytes','text','entry','name']},
            dict(kind=10,minimumStack=12,data=17,bss=20,textBytes=28,text=40,entry=43,name=52))

    def test_grouped_pointers_and_arrays_follow_a_changed_source_record(self):
        source=(ROOT/'lib/dos/programimage.act').read_text()
        old=layout(source.replace('  CARD minimumStack\n','').replace('\n','\r\n'))
        self.assertEqual(old['size'],72)
        self.assertEqual(old['fields']['data']['offset'],14)
        self.assertEqual(old['fields']['bss']['offset'],17)
        self.assertEqual(old['fields']['text']['offset'],36)
        self.assertEqual(old['fields']['name']['size'],24)
