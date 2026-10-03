import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from input_diagnostics import select
from input_registration_checks import reachable


class InputDiagnosticSelectionTests(unittest.TestCase):
    def test_reachability_handles_shared_helpers_cycles_and_terminal_calls(self):
        graph = dict(read=['helper'], helper=['read', 'writable'], acquire=['extent'])
        self.assertEqual(reachable(graph, 'read'), {'read', 'helper', 'writable'})
        self.assertEqual(reachable(graph, 'acquire'), {'acquire', 'extent'})

    def test_only_explicit_audits_change(self):
        source = 'before\r\n; INPUT_DIAGNOSTIC_BEGIN\r\naudit\r\n; INPUT_DIAGNOSTIC_END\r\nafter\r\n'
        self.assertEqual(select(source, False), 'before\nafter\n')
        self.assertEqual(select(source, True), 'before\naudit\nafter\n')

    def test_malformed_markers_and_nonboolean_option_fail(self):
        for source in ('; INPUT_DIAGNOSTIC_BEGIN\n', '; INPUT_DIAGNOSTIC_END\n',
                       '; INPUT_DIAGNOSTIC_BEGIN\n; INPUT_DIAGNOSTIC_BEGIN\n'):
            for enabled in (False, True):
                with self.subTest(source=source, enabled=enabled), self.assertRaises(ValueError):
                    select(source, enabled)
        for option in (0, 1, None, 'false'):
            with self.subTest(option=option), self.assertRaises(ValueError):
                select('', option)
