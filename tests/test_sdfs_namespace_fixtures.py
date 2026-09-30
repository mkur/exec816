import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from sdfs_namespace_fixtures import padded
class NamespaceFixtures(unittest.TestCase):
    def test_pinned_derivatives_and_independent_file_bytes(self):
        folder=ROOT/'tests/fixtures/sdfs'
        source=json.loads((folder/'reference.json').read_text())
        record=json.loads((folder/'namespace-reference.json').read_text())
        for case in record['fixtures']:
            size=case['sector_bytes'];original=folder/f'sdfs-21-{size}.atr';raw=(folder/case['image']).read_bytes()
            with self.subTest(sector_bytes=size):
                self.assertEqual(hashlib.sha256(raw).hexdigest(),case['sha256'])
                self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),case['source_sha256'])
                regenerated,mutation=padded(original.read_bytes());self.assertEqual(regenerated,raw);self.assertEqual(mutation,case['mutation'])
                expected=next(c for c in source['fixtures'] if c['sector_bytes']==size and c['revision']==33)
                self.assertEqual(case['files'],expected['files'])
                self.assertGreater(len(mutation['map_sectors']),1)
                self.assertEqual(mutation['live_entries'],300)
                self.assertEqual(mutation['last_ordinal'],1409)
if __name__=='__main__':unittest.main()
