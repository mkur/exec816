"""The passive heap observer rejects corrupt accounting and linked extents."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from qed_coexist_observe import heap_snapshot


class CoexistHeap(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(0x20100)
        self.storage = dict(BASE=0x100, HEADERS=0x120, BYTES=64, CAPACITY=1)
        self.put(0x120+14, 0x20000, 3); self.put(0x120+17, 0x20000, 3)
        self.put(0x120+20, 0x20100, 4); self.put(0x120+24, 256, 4)
        self.put(0x20000+4, 256, 4)

    def put(self, at, value, size):
        self.data[at:at+size] = value.to_bytes(size, 'little')

    def observe(self):
        return heap_snapshot(lambda at, n: bytes(self.data[at:at+n]), self.storage)

    def test_whole_and_fragmented_region(self):
        self.assertEqual(self.observe()['largest_bytes'], 256)
        self.put(0x20000, 0x20080, 3); self.put(0x20000+4, 64, 4)
        self.put(0x20080+4, 128, 4); self.put(0x120+24, 192, 4)
        r = self.observe()
        self.assertEqual((r['free_bytes'], r['largest_bytes'], r['free_extents']), (192, 128, 2))

    def test_cycle(self):
        self.put(0x20000, 0x20000, 3)
        with self.assertRaisesRegex(RuntimeError, 'pointer/order'): self.observe()

    def test_overlap(self):
        self.put(0x20000, 0x20080, 3)
        with self.assertRaisesRegex(RuntimeError, 'pointer/order'): self.observe()

    def test_accounting(self):
        self.put(0x120+24, 248, 4)
        with self.assertRaisesRegex(RuntimeError, 'accounting'): self.observe()

    def test_extent_bounds(self):
        self.put(0x20000+4, 264, 4)
        with self.assertRaisesRegex(RuntimeError, 'extent'): self.observe()

    def test_unaligned(self):
        self.put(0x20000+4, 255, 4)
        with self.assertRaisesRegex(RuntimeError, 'extent'): self.observe()

    def test_fully_allocated(self):
        self.put(0x120+14, 0, 3); self.put(0x120+24, 0, 4)
        self.assertEqual(self.observe()['free_extents'], 0)


if __name__ == '__main__': unittest.main()
