import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_console_view import files, layout


class ConsoleViewTests(unittest.TestCase):
    def test_generated_contract(self):
        for path, content in files().items():
            self.assertEqual(path.read_text(), content)
        self.assertEqual(layout()['Snapshot']['size'], 92)
        self.assertEqual(layout()['Snapshot']['fields']['cells'], 24)
        self.assertEqual(layout()['Input']['size'], 76)
