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
        for name in ('LICENSE', 'LICENSE-MIT', 'LICENSING.md', 'docs/demo-distribution.txt',
                     'docs/bitmap-shell-distribution.txt', 'docs/text-shell-distribution.txt'):
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

    def test_disposable_workspace_is_checked_and_packaged(self):
        content = b'disposable writable disk'
        (self.bundle/'work.atr').write_bytes(content)
        path = self.bundle/'of816.json'
        record = json.loads(path.read_text())
        record['additional_media'] = [dict(name='work.atr', sha256=hashlib.sha256(content).hexdigest())]
        path.write_text(json.dumps(record))
        with patch.object(package_demo, 'ROOT', self.root):
            package_demo.package(self.bundle, self.archive)
            with zipfile.ZipFile(self.archive) as archive:
                self.assertEqual(archive.read('exec816-demo/work.atr'), content)
            (self.bundle/'work.atr').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed demo artifact'):
                package_demo.package(self.bundle, self.archive)

    def graphics(self):
        folder=self.root/'graphics'
        folder.mkdir()
        files={name:('graphics '+name).encode() for name in package_demo.GEM_FILES}
        for name,content in files.items(): (folder/name).write_bytes(content)
        (folder/'debug.lst').write_text('Development only')
        (folder/'graphics.json').write_text(json.dumps(dict(diagnostic=False,
            files={name:hashlib.sha256(content).hexdigest() for name,content in files.items()})))
        return folder,files

    def test_optional_graphics_preserves_default_boot_and_checksums(self):
        graphics,expected=self.graphics()
        with patch.object(package_demo,'ROOT',self.root):
            package_demo.package(self.bundle,self.archive,graphics)
        with zipfile.ZipFile(self.archive) as archive:
            files={name.removeprefix('exec816-demo/'):archive.read(name) for name in archive.namelist()}
        self.assertEqual(files['Exec-of816.xex'],self.boot_files['Exec-of816.xex'])
        self.assertEqual(files['system.atr'],self.boot_files['system.atr'])
        self.assertIn('gem-vdi/graphics.atr',files)
        self.assertNotIn('gem-vdi/system.atr',files)
        self.assertEqual({name.removeprefix('gem-vdi/'):content for name,content in files.items()
            if name.startswith('gem-vdi/')},expected)
        checksums=dict(line.split('  ',1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
        self.assertEqual(set(checksums),set(files)-{'SHA256SUMS'})
        for name,digest in checksums.items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(),digest)
        self.assertIn(b'gem-vdi/README.txt',files['README.txt'])

    def test_changed_optional_graphics_prevents_distribution(self):
        graphics,_=self.graphics()
        (graphics/'Exec-gem-vdi.xex').write_bytes(b'changed')
        with patch.object(package_demo,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'Changed graphics artifact'):
                package_demo.package(self.bundle,self.archive,graphics)
        self.assertFalse(self.archive.exists())

    def bitmap(self):
        folder=self.root/'bitmap'
        folder.mkdir()
        files={name:('bitmap '+name).encode() for name in package_demo.BITMAP_FILES}
        for name,content in files.items(): (folder/name).write_bytes(content)
        (folder/'debug.lst').write_text('Development only')
        (folder/'bitmap.json').write_text(json.dumps(dict(diagnostic=False,
            files={name:hashlib.sha256(content).hexdigest() for name,content in files.items()})))
        return folder,files

    def test_bitmap_preserves_standard_boot_and_matching_media(self):
        bitmap,expected=self.bitmap()
        with patch.object(package_demo,'ROOT',self.root):
            package_demo.package(self.bundle,self.archive,bitmap=bitmap)
        with zipfile.ZipFile(self.archive) as archive:
            files={name.removeprefix('exec816-demo/'):archive.read(name) for name in archive.namelist()}
        self.assertEqual(files['Exec-of816.xex'],self.boot_files['Exec-of816.xex'])
        self.assertEqual(files['system.atr'],self.boot_files['system.atr'])
        self.assertEqual({name.removeprefix('bitmap-console/'):content for name,content in files.items()
            if name.startswith('bitmap-console/')},expected)
        checksums=dict(line.split('  ',1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
        self.assertEqual(set(checksums),set(files)-{'SHA256SUMS'})
        for name,digest in checksums.items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(),digest)
        self.assertIn(b'bitmap-console/README.txt',files['README.txt'])

    def test_changed_bitmap_media_prevents_distribution(self):
        bitmap,_=self.bitmap()
        (bitmap/'system.atr').write_bytes(b'wrong disk')
        with patch.object(package_demo,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'Changed bitmap artifact'):
                package_demo.package(self.bundle,self.archive,bitmap=bitmap)
        self.assertFalse(self.archive.exists())

    def test_diagnostic_bitmap_prevents_distribution(self):
        bitmap,_=self.bitmap()
        path=bitmap/'bitmap.json';record=json.loads(path.read_text())
        record['diagnostic']=True;path.write_text(json.dumps(record))
        with patch.object(package_demo,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'diagnostic bitmap'):
                package_demo.package(self.bundle,self.archive,bitmap=bitmap)
        self.assertFalse(self.archive.exists())

    def test_missing_licence_prevents_distribution(self):
        (self.root/'LICENSE-MIT').unlink()
        with patch.object(package_demo, 'ROOT', self.root):
            with self.assertRaises(FileNotFoundError):
                package_demo.package(self.bundle, self.archive)
        self.assertFalse(self.archive.exists())

    def text_shell(self):
        source=self.root/'shell';source.mkdir()
        manifest=source/'demo-manifest.json'
        manifest.write_text(json.dumps(dict(shell_only=True,
            artifacts={'program.xex':'native-image-digest'})))
        path=self.bundle/'of816.json';record=json.loads(path.read_text())
        record['exec_xex_sha256']='native-image-digest'
        record['media']['manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
        path.write_text(json.dumps(record))
        return source

    def test_text_shell_package_describes_manual_primes_and_keeps_boot_files(self):
        source=self.text_shell()
        with patch.object(package_demo,'ROOT',self.root):
            package_demo.package(self.bundle,self.archive,text_shell=source)
        with zipfile.ZipFile(self.archive) as archive:
            files={name.removeprefix('exec816-demo/'):archive.read(name) for name in archive.namelist()}
        self.assertEqual(set(files),set(self.boot_files)|set(package_demo.LICENSE_FILES)|
                         {'README.txt','SHA256SUMS'})
        self.assertIn(b'40 by 24',files['README.txt'])
        self.assertIn(b'No prime task is started',files['README.txt'])
        self.assertIn(b'RUN PRIMES',files['README.txt'])
        self.assertNotIn(b'@SYSTEM_',files['README.txt'])
        for name,content in self.boot_files.items():
            self.assertEqual(files[name],content)
        sums=dict(line.split('  ',1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
        self.assertEqual(set(sums),set(files)-{'SHA256SUMS'})
        for name,digest in sums.items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(),digest)

    def test_text_shell_rejects_a_boot_image_wrapping_another_native_build(self):
        source=self.text_shell()
        path=self.bundle/'of816.json';record=json.loads(path.read_text())
        record['exec_xex_sha256']='another-native-image'
        path.write_text(json.dumps(record))
        with patch.object(package_demo,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'OF816 does not wrap this text shell'):
                package_demo.package(self.bundle,self.archive,text_shell=source)
        self.assertFalse(self.archive.exists())

    def test_shell_only_boot_includes_notices_without_an_optional_demo(self):
        source=self.root/'shell';source.mkdir()
        artifacts={'program.xex':'native-image-digest'}
        for name in package_demo.GEM_NOTICES:
            content=('notice '+name).encode()
            (source/name).write_bytes(content)
            artifacts[name]=hashlib.sha256(content).hexdigest()
        manifest=source/'demo-manifest.json'
        manifest.write_text(json.dumps(dict(bitmap=True,shell_only=True,artifacts=artifacts)))
        path=self.bundle/'of816.json';record=json.loads(path.read_text())
        record['exec_xex_sha256']=artifacts['program.xex']
        record['media']['manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
        path.write_text(json.dumps(record))
        with patch.object(package_demo,'ROOT',self.root):
            package_demo.package(self.bundle,self.archive,bitmap_shell=source)
        with zipfile.ZipFile(self.archive) as archive:
            files={name.removeprefix('exec816-demo/'):archive.read(name) for name in archive.namelist()}
        self.assertEqual(set(files),set(self.boot_files)|set(package_demo.LICENSE_FILES)|
                         set(package_demo.GEM_NOTICES)|{'README.txt','SHA256SUMS'})
        self.assertIn(b'No prime task is started',files['README.txt'])
        self.assertNotIn(b'@SYSTEM_',files['README.txt'])
        sums=dict(line.split('  ',1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
        self.assertEqual(set(sums),set(files)-{'SHA256SUMS'})
        for name,digest in sums.items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(),digest)
        (source/'GEM-FONT-NOTICE.txt').write_text('changed')
        with patch.object(package_demo,'ROOT',self.root):
            with self.assertRaisesRegex(ValueError,'Changed bitmap shell notice'):
                package_demo.package(self.bundle,self.archive,bitmap_shell=source)


if __name__ == '__main__':
    unittest.main()
