import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from sdx_file import FormatError
from sdx_elsax_audit import audit, formatter_records, inventory, validate_widths


def compact(payload=b'\x22\x00\x00\x00', allocated=8):
    return struct.pack('<HBBHH', 0xfff9, 1, 0x43, len(payload) & 65535, allocated & 65535)+payload


def imported(name='H_PRINTF', site=1, stream=None):
    stream = stream if stream is not None else bytes([0xfe, 1, site, 0xfc])
    return struct.pack('<H', 0xfffb)+name.encode().ljust(8, b' ')+struct.pack('<H', len(stream))+stream


class ElsaxAuditTests(unittest.TestCase):
    def test_compact_and_low_memory_bss(self):
        raw = compact()+struct.pack('<HBBHH', 0xfffe, 2, 0xc0, 0, 1296)
        result = inventory(raw)
        self.assertEqual([(b['loaded_bytes'], b['allocated_bytes'], b['memory_index'], b['alignment'])
                          for b in result['blocks']], [(4, 8, 3, 256), (0, 1296, 0, 256)])
        self.assertEqual(sum(r['bytes'] for r in result['records']), len(raw))

    def test_compact_zero_size_means_complete_bank(self):
        block = inventory(compact(bytes(65536), 65536))['blocks'][0]
        self.assertEqual((block['loaded_bytes'], block['allocated_bytes']), (65536, 65536))

    def test_reject_compact_payload_larger_than_allocation(self):
        with self.assertRaisesRegex(FormatError, 'compact block'):
            inventory(compact(allocated=3))

    def test_cross_bank_import_and_same_block_relocation_have_different_widths(self):
        external = inventory(compact()+imported())
        self.assertEqual(validate_widths(external, {'H_PRINTF': 3}), {'3': 1})
        internal = inventory(compact()+struct.pack('<HBH', 0xfffd, 1, 4)+b'\xfe\x01\x01\xfc')
        self.assertEqual(validate_widths(internal, {}), {'2': 1})

    def test_far_reference_must_fit_all_three_bytes(self):
        result = inventory(compact()+imported(site=2))
        with self.assertRaisesRegex(FormatError, 'Native fixup outside'):
            validate_widths(result, {'H_PRINTF': 3})

    def test_overlapping_fixups_fail(self):
        result = inventory(compact(bytes(8))+imported('FIRST', 1)+imported('SECOND', 3))
        with self.assertRaisesRegex(FormatError, 'Overlapping'):
            validate_widths(result, {'FIRST': 3, 'SECOND': 0})

    def test_implicit_absolute_segment_and_absolute_fixup(self):
        raw = struct.pack('<HHH', 0xfffa, 0x400, 0x403)+bytes(4)
        raw += struct.pack('<HHH', 0x2e2, 0x2e3, 0x400)
        raw += imported('LOW', stream=b'\xfd\x01\x04\xfc')
        result = inventory(raw)
        self.assertEqual([a['address'] for a in result['absolute_segments']], [0x400, 0x2e2])
        self.assertEqual(result['fixups'][0]['sites'], [dict(block=0, offset=0x401)])

    def test_missing_fixup_terminator_and_truncated_payload_fail(self):
        for raw in (compact()+imported(stream=b'\xfe\x01'), compact()[:-1]):
            with self.subTest(raw=raw):
                with self.assertRaises(FormatError):
                    inventory(raw)

    def test_native_exports_must_fit_allocated_extent(self):
        raw = compact()+struct.pack('<HBH', 0xfffc, 1, 8)+b'@MAIN   '
        with self.assertRaisesRegex(FormatError, 'Export outside'):
            inventory(raw)

    def test_weak_import_marker_is_not_part_of_symbol_name(self):
        raw = bytearray(imported('OPTION'))
        raw[9] |= 128
        result = inventory(compact()+raw)
        self.assertEqual(result['imports'], ['OPTION'])
        self.assertTrue(result['fixups'][0]['weak'])

    def test_unknown_application_is_not_given_a_pinned_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory)/'OTHER.COM'
            binary.write_bytes(compact())
            with self.assertRaisesRegex(FormatError, 'not the pinned'):
                audit(binary)

    def test_native_formatter_address_classes_and_variable_keyword_index(self):
        fmt = b'%!p %<d %*t\0'
        code = b'\x22\0\0\0'+fmt+bytes(8)
        fixes = [dict(base='H_PRINTF', sites=[dict(block=1, offset=1)])]
        record, = formatter_records(code, fixes)
        self.assertEqual(record['conversions'], [dict(kind='p', prefix='!'),
                                                dict(kind='d', prefix='<'),
                                                dict(kind='t', prefix='*')])
        self.assertEqual(len(record['operand_sites']), 4)

    def test_formatter_requires_complete_inline_operands(self):
        fixes = [dict(base='H_PRINTF', sites=[dict(block=1, offset=1)])]
        with self.assertRaisesRegex(FormatError, 'Inline operands outside'):
            formatter_records(b'\x22\0\0\0%*t\0\0\0', fixes)


if __name__ == '__main__':
    unittest.main()
