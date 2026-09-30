import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from heap_model import Pool,trace

class HeapModelTests(unittest.TestCase):
    def test_bank_prefix_and_linear_tail(self):
        p=Pool(0x4fff0,0x70000)
        self.assertEqual(p.allocate(65536,True),0x50000)
        self.assertEqual(p.allocate(16),0x4fff0)
        self.assertEqual(p.allocate(65537),0)
        p.release(0x50000,65536)
        self.assertEqual(p.allocate(65537),0x50000)
        self.assertEqual(p.free,[(0x60008,0x70000)])
    def test_private_subranges_and_overlap(self):
        p=Pool(0x40000,0x40040);p.allocate(64)
        p.release(0x40009,7)
        self.assertEqual(p.free,[(0x40008,0x40010)])
        with self.assertRaises(AssertionError):p.release(0x40008,8)
        p.release(0x40000,8);p.release(0x40010,48)
        self.assertEqual(p.available,64)
    def test_last_bank_and_wide_overflow(self):
        p=Pool(0xff0000,0x1000000)
        self.assertEqual(p.allocate(65536,True),0xff0000)
        p.release(0xff0000,65536)
        for n in [0,0xfffffff9,0xffffffff]:self.assertEqual(p.allocate(n),0)
        self.assertEqual(p.available,65536)
    def test_reproducible_trace(self):
        self.assertEqual(trace(),trace())
        self.assertGreater(len(trace()[0]),175)
        self.assertEqual(trace()[1][-1][1],131072)

if __name__=='__main__':unittest.main()
