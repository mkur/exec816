"""A demo recipient gets the licences, unchanged binaries and valid checksums."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import package_demo


class DemoPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'docs').mkdir()
        for name in ('LICENSE', 'LICENSE-MIT', 'LICENSING.md', 'docs/demo-distribution.txt'):
            (self.root/name).write_bytes((ROOT/name).read_bytes())
        self.bundle = self.root/'bundle'
        self.bundle.mkdir()
        self.boot_files = {
            'Exec-of816.xex': b'\xff\xff\x00\x20boot',
            'system.atr': b'\x96\x02disk',
            'altirraos-816.rom': b'ROM',
            'ALTIRRAOS-LICENSE.txt': b'ROM redistribution notice\n',
            'OF816-LICENSE.txt': b'OF816 redistribution notice\n',
        }
        for name, content in self.boot_files.items():
            (self.bundle/name).write_bytes(content)
        digest = lambda name: hashlib.sha256(self.boot_files[name]).hexdigest()
        record = {
            'xex_sha256': digest('Exec-of816.xex'),
            'media': {'name': 'system.atr', 'sha256': digest('system.atr')},
            'rom': {'name': 'altirraos-816.rom', 'sha256': digest('altirraos-816.rom'),
                    'license': 'ALTIRRAOS-LICENSE.txt',
                    'license_sha256': digest('ALTIRRAOS-LICENSE.txt')},
            'boot_config': {'system_drive': 1},
        }
        (self.bundle/'of816.json').write_text(json.dumps(record))
        (self.bundle/'debug.lst').write_text('Not for distribution')
        self.archive = self.root/'demo.zip'

    def test_recipient_licences_and_checksums(self):
        with patch.object(package_demo, 'ROOT', self.root):
            package_demo.package(self.bundle, self.archive)
        with zipfile.ZipFile(self.archive) as archive:
            files = {name.removeprefix('exec816-demo/'): archive.read(name)
                     for name in archive.namelist()}
        self.assertEqual(set(files), set(self.boot_files) | {
            'README.txt', 'SHA256SUMS', 'EXEC816-GPL-3.0.txt',
            'EXEC816-MIT.txt', 'EXEC816-LICENSING.md'})
        for name, content in self.boot_files.items():
            self.assertEqual(files[name], content)
        for name, source in (('EXEC816-GPL-3.0.txt', 'LICENSE'),
                             ('EXEC816-MIT.txt', 'LICENSE-MIT'),
                             ('EXEC816-LICENSING.md', 'LICENSING.md')):
            self.assertEqual(files[name], (ROOT/source).read_bytes())
            self.assertIn(name.encode(), files['README.txt'])
        checksums = dict(line.split('  ', 1)[::-1]
                         for line in files['SHA256SUMS'].decode('ascii').splitlines())
        self.assertEqual(set(checksums), set(files) - {'SHA256SUMS'})
        for name, digest in checksums.items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest)
        self.assertNotIn(b'@SYSTEM_', files['README.txt'])

    def test_missing_licence_prevents_distribution(self):
        (self.root/'LICENSE-MIT').unlink()
        with patch.object(package_demo, 'ROOT', self.root):
            with self.assertRaises(FileNotFoundError):
                package_demo.package(self.bundle, self.archive)
        self.assertFalse(self.archive.exists())


if __name__ == '__main__':
    unittest.main()
