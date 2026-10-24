"""Local Altirra launchers preserve user settings and published demo media."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import launch_demo


class DemoLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.demo = self.root / 'demo with spaces'
        (self.demo / 'of816').mkdir(parents=True)
        self.config = self.root / 'settings.ini'
        self.original = '''[User\\AltirraSDL\\Profiles]
"Current profile" = 1
[User\\AltirraSDL\\Profiles\\00000001]
"_Category Mask" = "hardware,firmware,devices"
"_Saved Category Mask" = "hardware,firmware"
"_Parent" = 2
"Devices" = "[]"
"CPU: Clock multiplier" = 1
[User\\AltirraSDL\\Profiles\\00000002]
"_Category Mask" = "devices,mountedimages"
"_Saved Category Mask" = "devices,mountedimages"
[User\\AltirraSDL\\Profiles\\00000002\\Mounted Images]
"Disk 3" = "Wold-user-disk.atr"
"Cartridge 0" = "user-cart.car"
[User\\AltirraSDL\\Profiles\\00000000]
"Audio: Volume" = 83
"International font" = "żółw"
"Palette" = [01 02 FF]
'''
        self.config.write_bytes(self.original.replace('\n', '\r\n').encode())
        devices = [{'tag': 'hostfs', 'params': {'path1': '/Users/test/100% data/'}},
                   {'tag': 'vbxe', 'params': {'version': 127, 'alt_page': True}},
                   {'tag': 'kmkjzide2', 'params': {'enablesdx': True},
                    'buses': {'0': {'children': [{'tag': 'hdrawimage', 'params': {'path': 'user.img'}}]}}}]
        with self.config.open('a') as source:
            source.write('[User\\AltirraSDL\\Profiles\\00000002]\n"Devices" = ' + json.dumps(json.dumps(devices)) + '\n')
        self.original_bytes = self.config.read_bytes()
        self.record = {'pin': {'machine': {'video': 'PAL', 'high_banks': 63, 'clock_multiplier': 8}},
                       'media': 'system.atr', 'boot_image': 'of816/Exec-of816.xex',
                       'distribution': 'exec816-demo.zip'}
        (self.demo / 'of816/of816.json').write_text(json.dumps(
            {'rom': {'name': 'altirraos-816.rom'}, 'boot_config': {'system_drive': 1}}))
        for name in ('of816/altirraos-816.rom', 'of816/Exec-of816.xex', 'system.atr', 'work.atr'):
            (self.demo / name).write_bytes(name.encode())
        self.firmware = self.root / 'ide.rom'
        self.firmware.write_bytes(b'IDE BIOS')

    def prepare(self, cart=None, boot_mode=None):
        (self.demo / 'demo-manifest.json').write_text(json.dumps(self.record))
        home, args = launch_demo.prepare(self.demo, self.config, self.firmware, cart,boot_mode=boot_mode)
        self.assertEqual(self.config.read_bytes(), self.original_bytes)
        self.assertEqual((self.demo / 'work.atr').read_bytes(), b'work.atr')
        settings = launch_demo.read_settings(home / 'altirra/settings.ini')
        base = settings[launch_demo.PROFILES + r'\00000000']
        self.assertEqual(base['"Audio: Volume"'], '83')
        self.assertEqual(json.loads(base['"International font"']), 'żółw')
        self.assertEqual(base['"Palette"'], '[01 02 FF]')
        self.assertEqual(settings[launch_demo.PROFILES + r'\00000001']['"CPU: Clock multiplier"'], '8')
        device_profile = launch_demo.profile_owner(settings, 'devices')
        devices = json.loads(json.loads(settings[device_profile]['"Devices"']))
        mounted = settings[launch_demo.profile_owner(settings, 'mountedimages') + r'\Mounted Images']
        return settings, devices, mounted, args

    def test_sio_profile_and_persistent_work_copy(self):
        _, devices, mounted, args = self.prepare()
        self.assertEqual([d['tag'] for d in devices], ['hostfs', 'vbxe'])
        self.assertEqual(devices[1]['params'], {'version': 127, 'alt_page': True})
        self.assertEqual(set(mounted), {'"Disk 0"', '"Disk 7"'})
        self.assertEqual(json.loads(mounted['"Disk 0"']), 'R' + str(self.demo / 'system.atr'))
        work = Path(json.loads(mounted['"Disk 7"'])[1:])
        self.assertTrue(work.is_relative_to(self.demo / 'altirra'))
        work.write_bytes(b'my saved work')
        _, _, repeated, _ = self.prepare()
        self.assertEqual(repeated['"Disk 7"'], mounted['"Disk 7"'])
        self.assertEqual(work.read_bytes(), b'my saved work')
        self.assertEqual(args, ['--run', str(self.demo / 'of816/Exec-of816.xex')])

    def test_graphical_input_uses_port_two_in_the_inherited_profile(self):
        self.record['bitmap'] = True
        with self.config.open('a') as source:
            source.write('[User\\AltirraSDL\\Profiles\\00000002]\n'
                '"_Category Mask" = "devices,mountedimages,input"\n'
                '"_Saved Category Mask" = "devices,mountedimages,input"\n'
                '"Input: Active map names" = "Mouse -> ST Mouse (port 1)"\n'
                '"Input: Quick map names" = "Arrow Keys -> Joystick (port 1)"\n')
        self.original_bytes = self.config.read_bytes()
        settings, _, _, _ = self.prepare()
        profile = settings[launch_demo.profile_owner(settings, 'input')]
        self.assertEqual(json.loads(profile['"Input: Active map names"']),
                         'Mouse -> ST Mouse (port 2)')
        self.assertEqual(json.loads(profile['"Input: Quick map names"']), '')

    def test_mixed_ide_uses_readonly_fixture_and_sio(self):
        self.record['ideplus'] = {'access': 'readonly'}
        (self.demo / 'ideplus').mkdir()
        (self.demo / 'ideplus/ideplus.img').write_bytes(b'IDE')
        settings, devices, mounted, _ = self.prepare()
        ide = devices[-1]
        self.assertFalse(ide['params']['enablesdx'])
        image = ide['buses']['0']['children'][0]['params']
        self.assertEqual(image['path'], str(self.demo / 'ideplus/ideplus.img'))
        self.assertFalse(image['write_enabled'])
        self.assertEqual(set(mounted), {'"Disk 0"', '"Disk 7"'})
        self.assertEqual(json.loads(settings[launch_demo.FIRMWARE + r'\Default']['"kmkjzide2"']), str(self.firmware))

    def test_ide_only_copies_disk_and_keeps_old_work_after_rebuild(self):
        self.record['ide_only'] = True
        source = self.demo / 'ideplus.img'
        source.write_bytes(b'original SYS and WORK')
        _, devices, mounted, _ = self.prepare()
        self.assertEqual(dict(mounted), {})
        image = devices[-1]['buses']['0']['children'][0]['params']
        self.assertTrue(image['write_enabled'])
        work = Path(image['path'])
        work.write_bytes(b'user writes')
        _, again, _, _ = self.prepare()
        self.assertEqual(again[-1]['buses']['0']['children'][0]['params']['path'], str(work))
        self.assertEqual(work.read_bytes(), b'user writes')
        self.assertEqual(source.read_bytes(), b'original SYS and WORK')
        source.write_bytes(b'new build SYS and WORK')
        _, rebuilt, _, _ = self.prepare()
        self.assertNotEqual(rebuilt[-1]['buses']['0']['children'][0]['params']['path'], str(work))
        self.assertEqual(work.read_bytes(), b'user writes')

    def test_cart_boot_and_missing_media(self):
        with zipfile.ZipFile(self.demo / 'exec816-demo.zip', 'w') as archive:
            archive.writestr('exec816-demo/cartridge/Exec-of816-atarimax-8mbit-new.car', b'cart')
        _, _, _, args = self.prepare('new')
        self.assertEqual(args[0], '--cart')
        self.assertEqual(Path(args[1]).read_bytes(), b'cart')
        (self.demo / 'system.atr').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing demo input'):
            self.prepare()

    def test_combined_atr_xex_and_cart_share_one_writable_disk_with_qed_separate(self):
        self.record.update(bootable_atr=True,media='exec816.atr',boot_image='of816/exec816.atr',
            additional_media=[dict(name='qed.atr',drive=2,access='readonly')])
        for name in ('exec816.atr','of816/exec816.atr','qed.atr'):
            (self.demo/name).write_bytes(name.encode())
        with zipfile.ZipFile(self.demo/'exec816-demo.zip','w') as archive:
            archive.writestr('exec816-demo/cartridge/Exec-of816-atarimax-8mbit-new.car',b'cart')
        selected=None
        for mode,cart in ((None,None),('xex',None),(None,'new')):
            _,_,mounted,args=self.prepare(cart,mode)
            self.assertEqual(set(mounted),{'"Disk 0"','"Disk 1"'})
            disk=Path(json.loads(mounted['"Disk 0"'])[1:])
            self.assertEqual(json.loads(mounted['"Disk 1"']),'R'+str(self.demo/'qed.atr'))
            if selected is None:
                selected=disk;selected.write_bytes(b'saved WORK directory')
            self.assertEqual(disk,selected)
            self.assertEqual(disk.read_bytes(),b'saved WORK directory')
            if mode=='xex':self.assertEqual(Path(args[1]),self.demo/'of816/Exec-of816.xex')
            elif cart:self.assertEqual(args[0],'--cart')
            else:self.assertEqual(Path(args[1]),disk)

    def test_wrapper_handles_paths_and_forwards_arguments(self):
        tools = self.root / 'checkout with spaces/tools'
        tools.mkdir(parents=True)
        (tools / 'launch_demo.py').write_text('import sys\nprint(repr(sys.argv[1:]))\n')
        with patch.object(launch_demo, 'ROOT', tools.parent):
            launcher = launch_demo.write_launcher(self.demo)
        result = subprocess.run([str(launcher), '--config', 'custom path.ini', '--prepare-only'],
                                check=True, capture_output=True, text=True, cwd='/')
        self.assertIn(repr(['--demo', str(self.demo), '--config', 'custom path.ini', '--prepare-only']), result.stdout)
        self.assertTrue(os.access(launcher, os.X_OK))


if __name__ == '__main__':
    unittest.main()
