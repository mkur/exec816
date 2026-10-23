"""Host regressions for the standalone reference's saved work and provenance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_qed_reference as builder
from qed_reference import launch


class QEDReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bundle = self.root / 'reference with spaces'
        self.bundle.mkdir()
        self.media = {}
        for name in builder.PIN['media']:
            path = self.bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ('fixture: ' + name).encode()
            path.write_bytes(raw)
            self.media[name] = builder.digest(raw)
        (self.bundle / 'profile.json').write_text(json.dumps({'media': self.media}))

    def settings(self, config):
        parser = launch.configparser.ConfigParser(interpolation=None, delimiters=('=',))
        parser.optionxform = str
        parser.read(config / 'altirra/settings.ini')
        return parser

    def test_saved_disks_survive_repeated_preparation_and_relocation(self):
        normal_config = self.root / 'normal-settings.ini'
        normal_config.write_bytes(b'user configuration')
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root)}):
            launch.prepare(self.bundle)
            work = self.bundle / 'runtime/disks/qed.atr'
            work.write_bytes(b'saved user document')
            launch.prepare(self.bundle)
            self.assertEqual(work.read_bytes(), b'saved user document')
            moved = self.root / 'moved reference with spaces'
            shutil.move(self.bundle, moved)
            config, command = launch.prepare(moved)
        self.assertEqual(normal_config.read_bytes(), b'user configuration')
        settings = self.settings(config)
        mounts = settings[launch.PROFILES + r'\00000000\Mounted Images']
        for i, name in enumerate(('mydos-boot.atr', 'qed.atr')):
            self.assertEqual(json.loads(mounts[f'"Disk {i}"']),
                             'W' + str(moved / 'runtime/disks' / name))
        self.assertEqual((moved / 'runtime/disks/qed.atr').read_bytes(), b'saved user document')
        self.assertEqual(json.loads(settings[launch.FIRMWARE + r'\Default']['"kernelxl"']),
                         str(moved / 'firmware/altirraos-816.rom'))
        self.assertEqual(command[-2:], ['--cart', str(moved / 'GEM4XE.car')])

    def test_damaged_template_rejected_before_seeding_saved_disks(self):
        (self.bundle / 'qed.atr').write_bytes(b'corrupt template')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            launch.prepare(self.bundle)
        self.assertFalse((self.bundle / 'runtime').exists())

    def test_prepare_only_needs_no_emulator(self):
        shutil.copyfile(ROOT / 'tools/qed_reference/launch.py', self.bundle / 'launch.py')
        result = subprocess.run([sys.executable, str(self.bundle / 'launch.py'), '--prepare-only'],
                                env={**os.environ, 'PATH': '', 'ALTIRRA': '/missing/emulator'},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.bundle / 'runtime/config/altirra/settings.ini').exists())

    def test_changed_cached_download_is_rejected_without_network(self):
        path = self.root / 'cached.atr'
        path.write_bytes(b'changed')
        with patch.object(builder.urllib.request, 'urlopen') as request:
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                builder.fetch(path, 'https://example.invalid/disk', builder.digest(b'original'))
            request.assert_not_called()
        self.assertEqual(path.read_bytes(), b'changed')

    def test_archive_is_reproducible_and_retains_launcher_permissions(self):
        stage = self.root / 'stage'
        stage.mkdir()
        (stage / 'launch-gem4xe.command').write_bytes(b'#!/bin/sh\n')
        archive = self.root / 'one.zip'
        builder.write_zip(archive, stage)
        first = archive.read_bytes()
        os.utime(stage / 'launch-gem4xe.command', (1234567890, 1234567890))
        builder.write_zip(archive, stage)
        self.assertEqual(first, archive.read_bytes())
        with zipfile.ZipFile(archive) as zipped:
            self.assertIsNone(zipped.testzip())
            item = zipped.getinfo('gem4xe-altirra/launch-gem4xe.command')
            self.assertEqual((item.external_attr >> 16) & 0o777, 0o755)

    def test_media_pins_still_match_recorded_gui_walkthrough(self):
        evidence = json.loads((ROOT / builder.PIN['validated_emulator']['evidence']).read_text())
        self.assertEqual(builder.PIN['media'], evidence['media'])
        self.assertEqual(builder.PIN['validated_emulator']['sha256'], evidence['emulator']['sha256'])
        self.assertEqual(builder.ROM_PIN['sha256'], builder.PIN['media']['firmware/altirraos-816.rom'])


if __name__ == '__main__':
    unittest.main()
