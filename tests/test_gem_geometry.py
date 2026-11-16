"""Source contracts for the shared GEM records; execution uses the tiny probe."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import generate_gem_objects as gem
from generate_tasks import application_entry


class GemGeometryTests(unittest.TestCase):
    def test_shared_records(self):
        for path, expected in gem.files().items():
            self.assertEqual(path.read_text(), expected)
        self.assertEqual([gem.layout()[n]['size'] for n in ('Object','Text','Rect')],
                         [24,28,8])
        self.assertEqual(gem.layout()['Frame']['size'], 492)
        objects = (gem.ROOT/'c/include/gem/objects.h').read_text()
        self.assertIn('#include <gem/geometry.h>', objects)
        self.assertNotIn('} OBJECT;', objects)

    def test_library_entries(self):
        for module in ('GEMOBJECTS','GEMFRAME'):
            self.assertFalse(application_entry({'name':'M_'+module+'_CREATE_1234'}))
