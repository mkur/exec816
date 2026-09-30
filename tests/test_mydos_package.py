"""Independent original-MyDOS bytes and fail-closed metadata publication."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from mydos_fixtures import Image
from mydos_metadata_record import validate

class MyDOSPackageTests(unittest.TestCase):
    def test_original_media_and_known_bytes(self):
        manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
        for volume in manifest['volumes']:
            blob=(ROOT/volume['path']).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(),volume['sha256'])
            image=Image(blob)
            self.assertEqual(len(list(image.entries())),64)
            self.assertEqual(list(image.walk()),volume['entries'])
            self.assertEqual(volume['producer']['status'],'pass')
            self.assertEqual(volume['producer']['original_sha256'],manifest['original_sha256'])
            self.assertFalse({'DOS.SYS','DUP.SYS'} & {e['name'] for e in image.entries()})
            for entry in volume['files']:
                data,chain=image.file(entry)
                expected=bytes((i&255)^entry['seed'] for i in range(entry['bytes']))
                self.assertEqual(data,expected)
                self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])
                self.assertEqual(chain,entry['chain'])
            if image.size==256:
                large=next(e for e in volume['files'] if e['name']=='LARGE.BIN')
                self.assertGreater(large['bytes'],65535)
                self.assertTrue(large['flags']&4)
                self.assertTrue(any(b!=a+1 for a,b in zip(large['chain'],large['chain'][1:])))
            with self.assertRaises(RuntimeError):Image(blob[:-1])
            with self.assertRaises(RuntimeError):image.sector(image.count+1)

    def test_evidence_fails_closed(self):
        r=json.loads((ROOT/'docs/qualification/mydos-metadata.json').read_text());validate(r)
        for fault in ('mode','source','provider','disk','geometry','guard'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['cases'].pop()
            elif fault=='source':bad['inputs']['lib/mydos.act']='stale'
            elif fault=='provider':bad['cases'][0]['fixture_provider_sha256']='unknown'
            elif fault=='disk':bad['fixtures'][0]['sha256']='unknown'
            elif fault=='geometry':bad['cases'][0]['requests']=[n for n in bad['cases'][0]['requests'] if n['phase']!=30]
            else:bad['cases'][0]['runtime']['guards']='corrupt'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(bad)
if __name__=='__main__':unittest.main()
