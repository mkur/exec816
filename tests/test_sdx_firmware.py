import hashlib
import sys
import unittest
from unittest.mock import patch
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_sdx_firmware import ROOT, OUTPUT, catalog, identify, product


class FirmwareCatalogTests(unittest.TestCase):
    def test_generated_catalog_is_current(self):
        self.assertEqual(OUTPUT.read_text(), product())
        self.assertEqual(len(catalog()['profiles']), 3)

    def test_full_file_and_visible_ranges_are_pinned(self):
        raw = bytes((i*37+i//251) & 255 for i in range(16384))
        profile = dict(name='fixture', sha256=hashlib.sha256(raw).hexdigest(),
                       visible_crc32=f'{zlib.crc32(raw[:4096]+raw[6144:]):08x}',
                       emulation_nmi=int.from_bytes(raw[0x3ffa:0x3ffc], 'little'),
                       emulation_irq=int.from_bytes(raw[0x3ffe:], 'little'))
        with patch('generate_sdx_firmware.catalog', return_value={'profiles':[profile]}):
            self.assertEqual(identify(raw)['name'], 'fixture')
            self.check_mutations(raw)

    def check_mutations(self, raw):
        for at in (0, 0x1000, 0x1800, 0x3ffa, 0x3fff):
            changed = bytearray(raw)
            changed[at] ^= 1
            with self.subTest(address=at), self.assertRaises(ValueError):
                identify(changed)

    def test_unknown_and_truncated_images_are_rejected(self):
        for raw in (bytes(16384), bytes(16383)):
            with self.assertRaises(ValueError):
                identify(raw)


if __name__ == '__main__':
    unittest.main()
