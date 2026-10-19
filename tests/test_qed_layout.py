"""Preserve all contributors in the real linker summary, including long paths."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_qed import units_from_listing

class QedLayoutTests(unittest.TestCase):
    def test_single_separator_and_archive_selection_note(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'link.lst'
            path.write_text('137  /long/path/137-analysis-traps.o -\n'
                '          >  chuge   00001d\n          >  farcode 00001c\n'
                '146  __vsprintf_nofloat.o   clib-lc-hd.a\n'
                '          # picked based on printf=nofloat\n'
                '          >  farcode 00111b\n          >  switch 000030\n')
            rows=units_from_listing(path)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['sections'],dict(chuge=29,farcode=28))
            self.assertIsNone(rows[0]['archive'])
            self.assertEqual(rows[1]['archive'],'clib-lc-hd.a')
            self.assertEqual(rows[1]['sections'],dict(farcode=4379,switch=48))
