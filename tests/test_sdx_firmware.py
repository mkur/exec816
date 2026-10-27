import hashlib
import sys
import unittest
from unittest.mock import patch
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_sdx_firmware import ROOT, OUTPUT, LABELS, catalog, identify, labels, product


class FirmwareCatalogTests(unittest.TestCase):
    def test_generated_catalog_is_current(self):
        self.assertEqual(OUTPUT.read_text(), product())
        self.assertEqual(LABELS.read_text(), labels())
        self.assertEqual(len(catalog()['profiles']), 3)

    def test_visible_classification_and_actual_full_file_identity(self):
        raw = bytes((i*37+i//251) & 255 for i in range(16384))
        profile = dict(name='fixture', sha256=hashlib.sha256(raw).hexdigest(),
                       visible_crc32=f'{zlib.crc32(raw[:4096]+raw[6144:]):08x}',
                       emulation_nmi=int.from_bytes(raw[0x3ffa:0x3ffc], 'little'),
                       emulation_irq=int.from_bytes(raw[0x3ffe:], 'little'))
        with patch('generate_sdx_firmware.catalog', return_value={
                'profiles':[profile], 'fallback':catalog()['fallback']}):
            self.assertEqual(identify(raw)['name'], 'fixture')
            self.check_mutations(raw)

    def check_mutations(self, raw):
        for at in (0, 0x1000, 0x1800, 0x3ffa, 0x3fff):
            changed = bytearray(raw)
            changed[at] ^= 1
            with self.subTest(address=at):
                result = identify(changed)
                if at == 0x1000:
                    self.assertEqual(result['name'], 'fixture')
                    self.assertFalse(result['file_sha256_matches'])
                else:
                    self.assertTrue(result['assumed'])
                    self.assertEqual(result['name'], 'xlos-assumed')
                self.assertEqual(result['sha256'], hashlib.sha256(changed).hexdigest())

    def test_unknown_image_is_assumed_xlos_and_truncation_is_rejected(self):
        result = identify(bytes(16384))
        self.assertEqual(result['id'], catalog()['fallback']['id'])
        self.assertTrue(result['assumed'])
        with self.assertRaises(ValueError):
            identify(bytes(16383))


if __name__ == '__main__':
    unittest.main()
