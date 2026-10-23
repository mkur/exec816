"""The selected runtime correction must preserve and verify installed inputs."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import calypsi_runtime

class CalypsiRuntime(unittest.TestCase):
    def fixture(self,root):
        source=root/'installed/src/lib/stdio/input.c';source.parent.mkdir(parents=True)
        source.write_bytes(b'/* original notice */\nint value;\n')
        header=source.parent.parent/'libc.h';header.write_bytes(b'/* pinned header */\n')
        edit=root/'fix.patch';edit.write_text('--- a/input.c\n+++ b/input.c\n@@ -1,2 +1,2 @@\n /* original notice */\n-int value;\n+int value=1;\n')
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        pin=root/'pin.json';pin.write_text(json.dumps(dict(sources={'src/lib/stdio/input.c':digest(source)},
            headers={'src/lib/libc.h':digest(header)},patches={'fix.patch':digest(edit)})))
        return source,header,pin

    def test_verified_separate_repeatable_correction(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,header,pin=self.fixture(root)
            with patch.object(calypsi_runtime,'PIN',pin),patch.object(calypsi_runtime,'ROOT',root):
                files,include,first=calypsi_runtime.prepare(root/'out',root/'installed')
                self.assertEqual(files[0].read_bytes(),b'/* original notice */\nint value=1;\n')
                self.assertEqual(source.read_bytes(),b'/* original notice */\nint value;\n')
                self.assertEqual(calypsi_runtime.prepare(root/'out',root/'installed')[2],first)

    def test_changed_installed_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,header,pin=self.fixture(root);header.write_bytes(b'changed')
            with patch.object(calypsi_runtime,'PIN',pin),patch.object(calypsi_runtime,'ROOT',root),self.assertRaisesRegex(RuntimeError,'Changed Calypsi runtime source/header'):
                calypsi_runtime.prepare(root/'out',root/'installed')

if __name__=='__main__':unittest.main()
