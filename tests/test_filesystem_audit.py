import sys
import unittest
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from filesystem_audit import Audit
from mydos_fixtures import Image


class AllocationAudit(unittest.TestCase):
    def test_native_mutation_fixtures(self):
        root = ROOT/'tests/fixtures/filesystem-write'
        record = json.loads((root/'reference.json').read_text())
        self.assertEqual({(r['format'], r['sector_bytes']) for r in record['fixtures']},
                         {('mydos', 128), ('mydos', 256), ('sdfs', 128), ('sdfs', 256)})
        for fixture in record['fixtures']:
            with self.subTest(image=fixture['image']):
                raw = (root/fixture['image']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture['media_sha256'])
                self.assertEqual(fixture['status'], 'pass')
                audit = Audit(raw)
                self.assertEqual(getattr(audit, fixture['format'])(), fixture['counts'])
                self.assertEqual({p: hashlib.sha256(b).hexdigest() for p, b in audit.files.items()},
                                 fixture['files'])
                self.assertEqual(audit.files['EMPTY'], b'')
                self.assertNotIn('DELETE.BIN', audit.files)
                self.assertNotIn('OLD.BIN', audit.files)

    def test_native_and_independent_fixtures(self):
        for format in ('mydos', 'sdfs'):
            for path in (ROOT/'tests/fixtures'/format).glob('*.atr'):
                with self.subTest(path=path.name):
                    audit = Audit(path.read_bytes())
                    result = getattr(audit, format)()
                    self.assertEqual(result['allocated'] + result['free'], result['sectors'])
                    self.assertGreater(result['files'], 0)

    def test_mydos_crosslink_and_wrong_free_count(self):
        original = (ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes()
        image = Image(original)
        entries = [e for e in image.entries() if not e['flags'] & 16 and e['count']]
        first, second = entries[:2]
        offset = image.offset(361 + second['ordinal']//8) + second['ordinal'] % 8 * 16
        image.data[offset + 3:offset + 5] = first['start'].to_bytes(2, 'little')
        with self.assertRaisesRegex(ValueError, 'also owned|ordinal|count'):
            Audit(image.data).mydos()
        image = Image(original)
        image.data[image.offset(360) + 3] ^= 1
        with self.assertRaisesRegex(ValueError, 'Free count'):
            Audit(image.data).mydos()

    def test_live_sector_marked_free(self):
        for format, file in [('mydos', 'mydos450-128.atr'), ('sdfs', 'sdfs-21-128.atr')]:
            image = Image((ROOT/'tests/fixtures'/format/file).read_bytes())
            if format == 'mydos':
                bitmap, sector, prefix = 360, 361, 10
            else:
                header = image.sector(1)
                bitmap = int.from_bytes(header[16:18], 'little')
                sector = int.from_bytes(header[9:11], 'little')
                prefix = 0
            image.data[image.offset(bitmap) + prefix + sector//8] |= 128 >> (sector % 8)
            with self.subTest(format=format), self.assertRaisesRegex(ValueError, 'Allocation mismatch'):
                getattr(Audit(image.data), format)()

    def test_incomplete_entries(self):
        image = Image((ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes())
        image.data[image.offset(361)] |= 1
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            Audit(image.data).mydos()


if __name__ == '__main__':
    unittest.main()
