"""Resolve local text PCs from linked bytes, including relocated calls."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mgview_text_trace import linked_section,source_point


class TextTraceTests(unittest.TestCase):
    listing=r'''.section farcode,text
    \ 000000          text:
    \ 000000 22......             jsl long:helper
0233 count=0;
    \ 000004 a90000               lda ##0
0248 if (!count) break;
    \ 000007 6b                   rtl
'''

    def test_local_function_uses_linked_code_and_source_offsets(self):
        code=bytes.fromhex('22abcdefa900006b')
        image=dict(symbols=dict(text=0x80000),segments=[
            dict(address=0x80000,bytes=list(code),executable=False),
            dict(address=0x10000,bytes=list(b'\xff'*20+code),executable=True)])
        base,section=linked_section(image,self.listing,'text')
        self.assertEqual(base,0x10014)
        self.assertEqual(source_point(section,'count=0;'),4)
        self.assertEqual(source_point(section,'if (!count) break;'),7)

    def test_ambiguous_code_or_source_boundary_is_rejected(self):
        code=bytes.fromhex('22abcdefa900006b')
        image=dict(segments=[dict(address=0x10000,bytes=list(code+code),executable=True)])
        with self.assertRaises(RuntimeError):linked_section(image,self.listing,'text')
        with self.assertRaises(RuntimeError):source_point(self.listing+'count=0;','count=0;')
