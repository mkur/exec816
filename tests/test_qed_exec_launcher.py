"""The local QED launcher selects native hardware and keeps saved documents."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from launch_demo import write_qed_launcher as launcher
from launch_demo import read_settings, PROFILES, selected_work


class QedExecSetupTests(unittest.TestCase):
    def test_launch_with_spaces_and_preserve_saved_work(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve()/'QED preview';(out/'of816').mkdir(parents=True)
            (out/'demo-manifest.json').write_text(json.dumps(dict(bitmap=True,
                pin={'machine':{'video':'PAL','high_banks':63,'clock_multiplier':8}},
                media='system.atr',boot_image='of816/Exec-of816.xex')))
            (out/'of816/of816.json').write_text(json.dumps(dict(
                rom={'name':'altirraos-816.rom'},boot_config={'system_drive':1})))
            for name in ('system.atr','work.atr','of816/altirraos-816.rom','of816/Exec-of816.xex'):
                (out/name).write_bytes(name.encode())
            launcher(out)
            command=[str(out/'launch-qed.command'),'--altirra','/usr/bin/true','--prepare-only']
            subprocess.run(command,check=True,capture_output=True)
            settings=read_settings(out/'altirra/config/altirra/settings.ini')
            base=settings[PROFILES+r'\00000000']
            self.assertEqual(json.loads(base['"Input: Active map names"']),'Mouse -> ST Mouse (port 1)')
            self.assertEqual(base['"CPU: Clock multiplier"'],'8')
            self.assertEqual(base['"Memory: High banks"'],'63')
            self.assertEqual([d['tag'] for d in json.loads(json.loads(base['"Devices"']))],['vbxe'])
            images=settings[PROFILES+r'\00000000\Mounted Images']
            self.assertEqual(json.loads(images['"Disk 0"']),'R'+str(out/'system.atr'))
            work=Path(json.loads(images['"Disk 7"'])[1:]);work.write_bytes(b'saved document')
            (out/'work.atr').write_bytes(b'new clean template')
            launcher(out)
            subprocess.run(command,check=True,capture_output=True)
            self.assertEqual(work.read_bytes(),b'saved document')
            self.assertEqual((out/'work.atr').read_bytes(),b'new clean template')
            moved=out.parent/'Moved QED';shutil.move(out,moved)
            subprocess.run([str(moved/'launch-qed.command'),*command[1:]],check=True,capture_output=True)
            self.assertEqual((moved/'altirra/work.atr').read_bytes(),b'saved document')


class WorkSelectionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.demo=Path(temp.name).resolve();self.local=self.demo/'altirra';self.local.mkdir()
        (self.demo/'work.atr').write_bytes(b'template')

    def test_explicit_legacy_and_symlink_selection(self):
        saved=self.local/'work-oldhash.atr';saved.write_bytes(b'saved')
        with self.assertRaisesRegex(ValueError,'no selection'):
            selected_work(self.demo,self.local)
        alias=self.local/'selected.atr';alias.symlink_to(saved.name)
        self.assertEqual(selected_work(self.demo,self.local,alias),alias)
        (self.demo/'work.atr').write_bytes(b'replacement template')
        self.assertEqual(selected_work(self.demo,self.local),alias)
        self.assertEqual(saved.read_bytes(),b'saved')

    def test_missing_selected_disk_does_not_make_blank_replacement(self):
        saved=self.local/'old.atr';saved.write_bytes(b'saved')
        selected_work(self.demo,self.local,saved);saved.unlink()
        with self.assertRaisesRegex(ValueError,'Missing demo input'):
            selected_work(self.demo,self.local)
        self.assertFalse((self.local/'work.atr').exists())

    def test_template_and_readonly_selection_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'private disk'):
            selected_work(self.demo,self.local,self.demo/'work.atr')
        saved=self.local/'readonly.atr';saved.write_bytes(b'saved');saved.chmod(0o444)
        self.addCleanup(lambda:saved.chmod(0o644))
        with self.assertRaisesRegex(ValueError,'not writable'):
            selected_work(self.demo,self.local,saved)
        self.assertEqual(saved.read_bytes(),b'saved')
        self.assertFalse((self.local/'workspace.json').exists())

    def test_external_selection_survives_workspace_relocation(self):
        with tempfile.TemporaryDirectory() as external:
            saved=Path(external).resolve()/'external.atr';saved.write_bytes(b'saved')
            selected_work(self.demo,self.local,saved)
            moved=self.demo/'moved';shutil.move(self.local,moved)
            self.assertEqual(selected_work(self.demo,moved),saved)
            self.assertEqual(saved.read_bytes(),b'saved')

    def test_ambiguous_legacy_images_are_preserved(self):
        for name in ('work-one.atr','work-two.atr'):(self.local/name).write_bytes(name.encode())
        with self.assertRaisesRegex(ValueError,'select --work explicitly'):
            selected_work(self.demo,self.local)
        self.assertEqual(len(list(self.local.glob('*.atr'))),2)


    def test_unwritable_workspace_preserves_template(self):
        self.local.chmod(0o555);self.addCleanup(lambda:self.local.chmod(0o755))
        with self.assertRaisesRegex(ValueError,'workspace is not writable'):
            selected_work(self.demo,self.local)
        self.assertEqual((self.demo/'work.atr').read_bytes(),b'template')
        self.assertFalse((self.local/'work.atr').exists())

    def test_known_prior_private_mount_can_be_adopted(self):
        saved=self.local/'work-knownhash.atr';saved.write_bytes(b'saved')
        previous=self.local/'config/altirra/settings.ini';previous.parent.mkdir(parents=True)
        previous.write_text('['+PROFILES+r'\00000000\Mounted Images'+']\n"Disk 7" = '+json.dumps('W'+str(saved))+'\n')
        self.assertEqual(selected_work(self.demo,self.local),saved)
        self.assertEqual(json.loads((self.local/'workspace.json').read_text())['path'],saved.name)
