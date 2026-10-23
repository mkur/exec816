"""The source boundary must reject changed inputs and keep work/cache separate."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_qed

class QedSources(unittest.TestCase):
    def fixture(self,base):
        port=base/'port';port.mkdir();(port/'native').mkdir()
        cache=base/'cache';source=cache/'qed/src/example.c';source.parent.mkdir(parents=True)
        raw=b'/* original */\r\n';source.write_bytes(raw)
        pin=dict(sources=[dict(id='qed',repository='unused',revision='f'*40,tree='a'*40,
            files={'src/example.c':hashlib.sha256(raw).hexdigest()})],exec_baseline=dict(input_files={}))
        (port/'inputs.json').write_text(json.dumps(pin))
        return port,cache,source,raw

    def test_exact_bytes_and_repeatable_work_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);port,cache,source,raw=self.fixture(base)
            with patch.object(prepare_qed,'PORT',port):
                before=prepare_qed.prepare(base/'work',cache)
                copy=base/'work/source/qed/src/example.c'
                self.assertEqual(copy.read_bytes(),raw)
                copy.write_bytes(b'local changes')
                self.assertEqual(source.read_bytes(),raw)
                self.assertEqual(prepare_qed.prepare(base/'work',cache),before)
                self.assertEqual(copy.read_bytes(),raw)

    def test_changed_cache_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);port,cache,source,raw=self.fixture(base);source.write_bytes(raw+b'changed')
            with patch.object(prepare_qed,'PORT',port),self.assertRaisesRegex(RuntimeError,'Changed QED source'):
                prepare_qed.prepare(base/'work',cache)

    def test_work_cannot_alias_or_contain_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);port,cache,source,raw=self.fixture(base)
            for target in (cache,cache/'work',base):
                with patch.object(prepare_qed,'PORT',port),self.assertRaisesRegex(RuntimeError,'separate trees'):
                    prepare_qed.prepare(target,cache)

if __name__=='__main__':unittest.main()
