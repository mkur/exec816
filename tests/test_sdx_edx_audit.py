"""Failure and control-flow cases for the EDX host inventory, without binaries."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sdx_file import FormatError
from sdx_edx_audit import audit, decode, dispatch_tables


class EdxAuditTests(unittest.TestCase):
    def walk(self, data, imports=None, veneers=None, indirect=None, roots=None):
        memory = bytearray(65536)
        memory[0x2000:0x2000 + len(data)] = data
        return decode(memory, 0x2000, 0x2000 + len(data), roots or [0x2000],
                      imports or {}, veneers or {}, indirect or {})

    def test_branch_walks_both_arms_without_decoding_unreachable_data(self):
        code, _ = self.walk(bytes.fromhex('d003a90160a9026000'))
        self.assertEqual(sorted(code), [0x2000, 0x2002, 0x2004, 0x2005, 0x2007])

    def test_unknown_external_control_flow_is_rejected(self):
        with self.assertRaisesRegex(FormatError, 'outside initialized'):
            self.walk(bytes.fromhex('4c00f0'))

    def test_import_returns_but_failure_is_terminal(self):
        code, calls = self.walk(bytes.fromhex('2000f04c10f000'),
                                imports={0xF000: 'FCLOSE', 0xF010: 'U_FAIL'})
        self.assertEqual(sorted(code), [0x2000, 0x2003])
        self.assertEqual([call['symbol'] for call in calls], ['FCLOSE', 'U_FAIL'])

    def test_explicit_error_continuation_is_walked(self):
        code, _ = self.walk(bytes.fromhex('600060'), roots=[0x2000, 0x2002])
        self.assertEqual(sorted(code), [0x2000, 0x2002])

    def test_unreviewed_indirect_jump_is_rejected(self):
        with self.assertRaisesRegex(FormatError, 'Unreviewed indirect'):
            self.walk(bytes.fromhex('6c8700'))
        code, _ = self.walk(bytes.fromhex('6c8700'), indirect={0x2000: 0x87})
        self.assertEqual(len(code), 1)

    def test_mutated_rawcon_veneer_is_rejected(self):
        with self.assertRaisesRegex(FormatError, 'veneer differs'):
            self.walk(bytes.fromhex('4c00f0'), veneers={0x2000: 'put'})
        code, _ = self.walk(bytes.fromhex('4cffff'), veneers={0x2000: 'put'})
        self.assertEqual(code[0x2000]['rawcon'], 'put')

    def test_truncated_instruction_is_rejected(self):
        with self.assertRaisesRegex(FormatError, 'Truncated instruction'):
            self.walk(bytes.fromhex('a9'))

    def table_image(self):
        memory = bytearray(65536)
        for mode in range(3):
            memory[0x100 + 2 * mode:0x102 + 2 * mode] = (0x2100).to_bytes(2, 'little')
            memory[0x110 + mode] = 2
        # BREAK/default head, one matched key, and a final two-byte fallback.
        memory[0x2100:0x210A] = bytes.fromhex('0020880001201b000220')
        return memory

    def test_dispatch_includes_trailing_fallback(self):
        tables = dispatch_tables(self.table_image(), 0x100, 0x110, 0x2000, 0x2200)
        self.assertEqual(tables[0]['fallback'], 0x2002)
        self.assertTrue(tables[0]['entries'][0]['break_entry'])
        self.assertEqual(tables[0]['entries'][1]['key'], 27)

    def test_invalid_dispatch_fallback_is_rejected(self):
        memory = self.table_image()
        memory[0x2108:0x210A] = b'\x00\xF0'
        with self.assertRaisesRegex(FormatError, 'fallback outside'):
            dispatch_tables(memory, 0x100, 0x110, 0x2000, 0x2200)

    def test_dispatch_extent_includes_the_fallback_word(self):
        with self.assertRaisesRegex(FormatError, 'table outside'):
            dispatch_tables(self.table_image(), 0x100, 0x110, 0x2000, 0x2109)

    def test_unknown_application_cannot_use_reviewed_annotations(self):
        with self.assertRaisesRegex(FormatError, 'Unknown EDX application'):
            audit(b'\xFE\xFF' + bytes(16))


if __name__ == '__main__':
    unittest.main()
