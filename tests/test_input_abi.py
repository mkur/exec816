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
                         [32, 32, 24])
        self.assertEqual(layout['InputLease acquisition'], 12)
        self.assertEqual(layout['InputConfig filterCount'], 12)
        self.assertEqual(layout['InputEvent x'], 16)
        self.assertEqual(layout['InputConfig pointerProtocol'], 16)
        self.assertEqual(layout['InputConfig reserved2'], 28)

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

    def test_native_state_reuses_existing_task_arena_slack(self):
        import generate_input_native as native
        from generate_memory import layout
        import tempfile
        values, source = native.definitions()
        self.assertEqual(values['STATE_SIZE'],160)
        self.assertEqual(values['STATE_ROUTEFLAGS'],144)
        self.assertEqual(values['CAPTURE_ROUTEFLAGS'],41)
        self.assertEqual(values['CAPTURE_SIZE'],560)
        self.assertEqual(values['RAWEVENT_SIZE'],8)
        self.assertEqual((native.ROOT/'lib/input/inputnative.act').read_text(),source)
        memory=layout()
        before=copy.deepcopy(memory['runtime_reservations'])
        with tempfile.TemporaryDirectory() as output:
            native.generate(output,memory)
        self.assertEqual(memory['runtime_reservations'],before)
        self.assertLessEqual(memory['input_storage']['STATE']+values['STATE_SIZE'],memory['input_storage']['CAPTURE'])

    def test_pointer_storage_is_disjoint_and_guarded(self):
        import generate_input_native as native
        from generate_memory import layout
        import tempfile
        memory = layout()
        with tempfile.TemporaryDirectory() as output:
            native.generate(output, memory)
        storage = memory['input_storage']
        values, _ = native.definitions()
        from generate_sio_adapter import ABI as sio
        from generate_program import ABI as program
        self.assertLessEqual(sio['native_offset']+sio['native_reserved_bytes'], program['provider_offset'])
        self.assertEqual(values['POINTERSAMPLE_SIZE'], 28)
        self.assertEqual(values['POINTERCAPTURE_EVENTS'], 128)
        self.assertEqual(storage['POINTER_RESERVED_BYTES'], 2560)
        self.assertLessEqual(storage['POINTER_STATE']+values['STATE_SIZE'], storage['POINTER_RESERVE'])
        self.assertEqual(storage['POINTER_CAPTURE']-storage['POINTER_RESERVE'], 16)
        self.assertEqual(storage['POINTER_RESERVED_BYTES']-storage['POINTER_CAPTURE_BYTES']-32, 224)
