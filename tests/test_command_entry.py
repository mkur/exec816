"""Command fixture rewriting follows the function entry on LF and CRLF hosts."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import test_cat
import test_wc


class CommandEntryTests(unittest.TestCase):
    def test_instrumentation_preserves_body_and_return_on_both_newlines(self):
        for name, runner, entry in [('cat',test_cat,'CopyInput'),('wc',test_wc,'CountInput')]:
            source=(ROOT/f'examples/commands/{name}.act').read_text()
            expected=source.replace('LONGINT FUNC Main()',f'LONGINT FUNC {entry}()')
            for newline in ('\n','\r\n'):
                self.assertEqual(runner.command_source(source.replace('\n',newline)),expected)
            with self.assertRaisesRegex(RuntimeError,'Missing command entry'):
                runner.command_source(source.replace('LONGINT FUNC Main()','PROC Main()'))
