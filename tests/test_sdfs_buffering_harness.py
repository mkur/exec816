import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from mydos_fixtures import Image
from filesystem_audit import word
from test_filesystem_write_edges import entry
from test_filesystem_write_lifetime import named_stages, physical_stage


class BufferedWriteObservation(unittest.TestCase):
    def test_named_stages_and_map_limit(self):
        self.assertEqual(named_stages(128,2000),
                         {'payload-first':1,'payload-middle':8,'payload-last':16,
                          'bitmap':17,'header':18,'map':19,
                          'directory-first':20,'directory-last':20})
        with self.assertRaisesRegex(RuntimeError,'one primed file map'):
            named_stages(128,8192)

    def test_split_record_has_two_distinct_completion_points(self):
        stages = named_stages(128,17,split=True)
        self.assertEqual(stages['directory-first'],5)
        self.assertEqual(stages['directory-last'],6)

    def test_classification_from_native_fixture_geometry(self):
        for size in (128,256):
            image = Image((ROOT/f'tests/fixtures/filesystem-write/sdfs-{size}.atr').read_bytes())
            addresses,first,_ = entry(image,'sdfs','EMPTY')
            self.assertEqual(physical_stage(image,1,'EMPTY'),'header')
            self.assertEqual(physical_stage(image,word(image.sector(1),16),'EMPTY'),'bitmap')
            self.assertEqual(physical_stage(image,first,'EMPTY'),'map')
            directory = {(a-400)//size+4 for a in addresses}
            self.assertEqual(len(directory),2 if size == 128 else 1)
            for sector in directory:
                self.assertEqual(physical_stage(image,sector,'EMPTY'),'directory')
