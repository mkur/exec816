"""The local QED launcher selects native hardware and keeps saved documents."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from launch_demo import write_qed_launcher as launcher
from launch_demo import read_settings, PROFILES


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
            launcher(out)
            subprocess.run(command,check=True,capture_output=True)
            self.assertEqual(work.read_bytes(),b'saved document')
            self.assertEqual((out/'work.atr').read_bytes(),b'work.atr')
