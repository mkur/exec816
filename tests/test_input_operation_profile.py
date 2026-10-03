import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_input_operations import assembly_markers, operation_rows


class InputOperationProfileTests(unittest.TestCase):
    def test_classifies_nested_calls_without_summing_c_and_native_costs(self):
        def row(kind, start, end, a=0, x=0):
            return dict(kind=kind, start=start, end=end, return_a=a, return_x=x)
        spans = [row('seeded_keyboard', 0, 100), row('c_take', 1, 90),
                 row('take', 2, 80), row('source', 3, 4, 2),
                 row('raw_input_take', 5, 6, 65534, 65535)]
        rows = operation_rows(spans)
        self.assertEqual([r['outcome'] for r in rows], ['loss', 'loss'])
        self.assertEqual([r['source'] for r in rows], ['keyboard', 'keyboard'])
        self.assertTrue(all(r['keyboard_fixture'].startswith('seeded') for r in rows))
        spans[-1] = row('raw_input_take_break', 5, 6, 1)
        self.assertEqual(operation_rows(spans)[0]['outcome'], 'cancel')
        spans[3] = row('source', 3, 4, 3)
        spans[-1] = row('raw_pointer_take', 5, 6, 2)
        self.assertEqual(operation_rows(spans)[0]['outcome'], 'loss')
        spans.append(row('extent', 7, 8))
        with self.assertRaisesRegex(RuntimeError, 'full audit'):
            operation_rows(spans)

    def test_assembly_listing_boundaries_include_all_returns_but_not_operands(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output/'hosted.lst').write_text('''000010r 4               input_take:
000010r 4  A9 6B 00         lda #$6b
000013r 4  6B               rtl
000014r 4  EA               nop
000015r 4  6B               rtl
000016r 4               input_take_end:
''')
            program = dict(output=output, labels=dict(input_take=0x100, input_take_end=0x106),
                image=dict(segments=[dict(address=0x100, bytes=[0xa9, 0x6b, 0, 0x6b, 0xea, 0x6b])]))
            self.assertEqual(assembly_markers(program, ['input_take'])['raw_input_take']['returns'],
                             [0x103, 0x105])
            program['image']['segments'][0]['bytes'][-1] = 0
            with self.assertRaisesRegex(RuntimeError, 'disagrees'):
                assembly_markers(program, ['input_take'])
