import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from make_sdfs_fixtures import FIXTURES, Media, DAMAGE_CASES, damaged, jobs, pattern


class SDFSFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads((FIXTURES/'reference.json').read_text())

    def test_pinned_independent_readback(self):
        variants = set()
        for fixture in self.reference['fixtures']:
            with self.subTest(image=fixture['image']):
                raw = (FIXTURES/fixture['image']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture['sha256'])
                self.assertEqual(raw[48], fixture['revision'])
                self.assertEqual(Media(raw).size, fixture['sector_bytes'])
                self.assertEqual(fixture['original_readback']['status'], 'pass')
                self.assertEqual(fixture['original_readback']['sparse_gap_status'], 135)
                for job in jobs():
                    expected = pattern(job['size'], job['seed'], job.get('zero', False))
                    self.assertEqual(hashlib.sha256(expected).hexdigest(), fixture['files'][job['name']])
                self.assertEqual(sum(name.startswith('MANY/') for name in fixture['files']), 300)
                variants.add((fixture['revision'], fixture['sector_bytes']))
        self.assertEqual(variants, {(0x20, 128), (0x20, 256), (0x21, 128), (0x21, 256)})

    def test_damage_is_explicit_and_does_not_modify_reference(self):
        for fixture in self.reference['fixtures']:
            raw = (FIXTURES/fixture['image']).read_bytes()
            for case in DAMAGE_CASES:
                changed, offsets = damaged(raw, case)
                self.assertEqual(offsets, fixture['mutations'][case])
                self.assertNotEqual(changed, raw)
            self.assertEqual(raw, (FIXTURES/fixture['image']).read_bytes())


if __name__ == '__main__': unittest.main()
