"""A changed native ABI must be rejected before a media refresh writes anything."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_demo


class WorkbenchRefreshTests(unittest.TestCase):
    def test_native_abi_change_preserves_every_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            originals={'program.xex':b'native','system.atr':b'old disk',
                       'exec816-demo.zip':b'old distribution'}
            for name,raw in originals.items():(root/name).write_bytes(raw)
            inputs={name:build_demo.sha256(ROOT/name) for name in build_demo.FASTBASIC_NATIVE_INPUTS}
            inputs['abi/c-program.json']='changed ABI'
            record=dict(basic_workbench=True,fastbasic=dict(native_inputs=inputs),
                artifacts={name:hashlib.sha256(raw).hexdigest() for name,raw in originals.items()})
            original=(json.dumps(record)+'\n').encode()
            (root/'demo-manifest.json').write_bytes(original)
            with self.assertRaisesRegex(RuntimeError,'Native ABI/backend changed'):
                build_demo.refresh_workbench(root)
            self.assertEqual((root/'demo-manifest.json').read_bytes(),original)
            self.assertEqual({p.name:p.read_bytes() for p in root.iterdir() if p.name!='demo-manifest.json'},originals)
