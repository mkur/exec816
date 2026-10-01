"""Extraction must be reproducible and refuse unpinned or overlapping input."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import extract_gem_vdi as extraction


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.port = self.root/'port'
        (self.port/'patches').mkdir(parents=True)
        (self.port/'hosted').mkdir()
        (self.port/'hosted/hosted.h').write_text('/* host */\n')
        self.source = self.root/'upstream'
        self.source.mkdir()
        (self.source/'input.c').write_bytes(b'omitted\r\nkeep\r\nchange\r\n')
        (self.port/'patches/0001-hosted-storage-and-subset.patch').write_text(
            '--- a/src/input.c\n+++ b/src/input.c\n@@ -1,2 +1,2 @@\n keep\n-change\n+adapted\n')
        self.selection = dict(outputs={'src/input.c':dict(source='input.c',ranges=[[2,3]])})
        self.output = self.root/'result'

    def extract(self):
        (self.port/'selection.json').write_text(json.dumps(self.selection))
        with patch.object(extraction,'PORT',self.port), patch.object(extraction,'source_inputs',return_value={'input.c':{}}):
            return extraction.extract(self.output,self.source)

    def test_repeated_extraction_normalizes_text_and_has_stable_hashes(self):
        first = self.extract()
        self.assertEqual((self.output/'src/input.c').read_bytes(),b'keep\nadapted\n')
        self.assertEqual(first,self.extract())
        self.assertIn('src/hosted.h',first['adapted'])
        self.assertNotIn('extraction.json',first['adapted'])

    def test_bad_selections_fail_before_patch(self):
        for ranges in ([[0,2]],[[2,4]],[[2,3],[3,3]]):
            self.selection['outputs']['src/input.c']['ranges'] = ranges
            with self.subTest(ranges=ranges),self.assertRaisesRegex(RuntimeError,'source selection'):
                self.extract()
        self.selection['outputs']['src/input.c']['source'] = 'unknown.c'
        with self.assertRaisesRegex(RuntimeError,'Unpinned'):
            self.extract()

    def test_output_path_cannot_escape(self):
        self.selection['outputs'] = {'../escape':dict(source='input.c')}
        with self.assertRaisesRegex(RuntimeError,'escapes'):
            self.extract()

    def test_patch_context_drift_is_not_accepted(self):
        (self.source/'input.c').write_text('omitted\nwrong\nchange\n')
        with self.assertRaises(subprocess.CalledProcessError):
            self.extract()


if __name__ == '__main__':
    unittest.main()
