"""Keep the generated caller record current; emitted probes check C layout."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_aes_wait import files


class AESWaitABITests(unittest.TestCase):
    def test_generated_header_is_current(self):
        for path,content in files().items():self.assertEqual(path.read_text(),content)
