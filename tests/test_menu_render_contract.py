"""The presenter menu bridge has no retained widget-window operations."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import generate_menu_render as menu
class MenuPacket(unittest.TestCase):
    def test_generated_layout(self):
        for path,expected in menu.files().items():
            self.assertEqual(path.read_text(),expected,str(path))
        self.assertEqual({k for k in menu.ABI['constants'] if k.startswith('OP_')},{'OP_DRAW','OP_INVERT'})
