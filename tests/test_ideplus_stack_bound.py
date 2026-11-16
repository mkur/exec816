"""Relocated JSL operands may themselves contain $22 and a known address."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ideplus_stack_bound import direct_calls


class Calls(unittest.TestCase):
    def test_operand_is_not_a_second_call(self):
        # JSL $3f2249; REP #$20; JSL $123456. The operand's $22 would
        # otherwise appear to call the unrelated routine at $20c23f.
        body=bytes.fromhex('2249223fc22022563412')
        self.assertEqual(direct_calls(body,{0x3f2249,0x20c23f,0x123456}),
                         [0x3f2249,0x123456])

    def test_adjacent_calls(self):
        body=bytes.fromhex('2256341222563412')
        self.assertEqual(direct_calls(body,{0x123456}),[0x123456,0x123456])

    def test_stack_operand_is_not_a_call(self):
        # STA $22,S; LDA $20,S; CLC. This occurred in emitted Relative code
        # when an unrelated routine happened to land at $1820a3.
        self.assertEqual(direct_calls(bytes.fromhex('8322a32018'),{0x1820a3}),[])

    def test_width_changes_and_truncation(self):
        body=bytes.fromhex('a92200e220a922c22022563412')
        self.assertEqual(direct_calls(body,{0x123456}),[0x123456])
        with self.assertRaisesRegex(ValueError,'truncated'):
            direct_calls(bytes.fromhex('225634'),{0x123456})
