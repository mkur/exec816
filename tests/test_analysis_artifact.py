"""An analysis ELF cannot reach either demo filesystem under a renamed file."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analysis_artifact import MARKER
from make_data_disk import make

class AnalysisArtifactTests(unittest.TestCase):
    def test_both_media_producers_reject_renamed_analysis_payload(self):
        for filesystem in ('mydos','sdfs'):
            with self.subTest(filesystem=filesystem),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);source=root/'source';source.mkdir()
                (source/'OTHER.BIN').write_bytes(b'\x7fELF'+MARKER)
                with self.assertRaisesRegex(RuntimeError,'Analysis-only'):
                    make(root/'disk.atr',source,['OTHER.BIN'],filesystem=filesystem)
                self.assertFalse((root/'disk.atr').exists())
