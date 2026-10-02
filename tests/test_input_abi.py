import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_input import ABI, expected_layout, files, validate


class InputAbiTests(unittest.TestCase):
    def test_checked_in_definitions_and_selected_sizes(self):
        for path, content in files().items():
            self.assertEqual(path.read_text(), content, str(path))
        layout = dict(expected_layout())
        self.assertEqual([layout['Input'+name+' size'] for name in ('Lease', 'Config', 'Event')],
                         [32, 16, 24])
        self.assertEqual(layout['InputLease acquisition'], 12)
        self.assertEqual(layout['InputConfig filterCount'], 12)
        self.assertEqual(layout['InputEvent x'], 16)

    def test_overlapping_unaligned_and_duplicate_fields_rejected(self):
        for offset in (10, 11, 13, 14):
            abi = copy.deepcopy(ABI)
            abi['records']['Lease']['fields'][1][2] = offset
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                validate(abi)
        abi = copy.deepcopy(ABI)
        abi['records']['Event']['fields'][1][0] = 'acquisition'
        with self.assertRaises(ValueError):
            validate(abi)

    def test_truncated_and_padded_records_rejected(self):
        for name in ABI['records']:
            for delta in (-2, -1, 1, 2):
                abi = copy.deepcopy(ABI)
                abi['records'][name]['bytes'] += delta
                with self.subTest(name=name, delta=delta), self.assertRaises(ValueError):
                    validate(abi)

    def test_unsupported_alignment_rejected(self):
        abi = copy.deepcopy(ABI)
        abi['alignment'] = 4
        with self.assertRaises(ValueError):
            validate(abi)
