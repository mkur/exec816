import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from heap_model import System,system_trace


class HeapSystemModelTests(unittest.TestCase):
    def test_priority_then_address_and_holes(self):
        heap=System([(0x30000,0x50000,0,17),(0x70000,0xa0000,10,17),(0x10000,0x20000,0,17)])
        self.assertEqual(heap.allocate(0x30000,0x100000),0x70000)
        self.assertEqual(heap.allocate(0x10000),0x10000)
        self.assertEqual(heap.allocate(0x20001,0x100000),0)
        self.assertEqual(heap.memory_type(0x60000),0)

    def test_largest_uses_intersections_with_banks(self):
        heap=System([(0x4fff0,0x70000,0,17)])
        self.assertEqual(heap.query(0x20000),65536)
        self.assertEqual(heap.allocate(65536),0x50000)
        self.assertEqual(heap.query(0x120000),65536)
        self.assertEqual(heap.allocate(65536),0x60000)
        self.assertEqual(heap.query(0x20000),16)
        self.assertEqual(heap.query(),16)
        self.assertEqual(heap.query(0x80000),131088)

    def test_flag_failures_do_not_mutate(self):
        heap=System([(0xff0000,0x1000000,0,17)])
        for flags in (2,4,256,512,1024,0x18,0x100008,0x40000,0x20000000):
            self.assertEqual(heap.allocate(8,flags),0)
            self.assertEqual(heap.query(flags),0)
        self.assertEqual(heap.query(0xa0000),0)
        self.assertEqual(heap.query(0x80010000),65536)
        self.assertEqual(heap.memory_type(0xffffff),17)
        self.assertEqual(heap.allocate(65536),0xff0000)

    def test_system_trace_returns_all_storage(self):
        regions=[(0x40000,0x70000,0,17),(0x80000,0xd0000,10,17)]
        ops,snapshots=system_trace(regions)
        self.assertGreater(len(ops),130)
        self.assertEqual(snapshots[-1][1],0x80000)
        self.assertEqual((ops,snapshots),system_trace(regions))
