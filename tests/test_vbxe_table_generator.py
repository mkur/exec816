import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_vbxe_tables import generate, tables


class VbxeTables(unittest.TestCase):
    def test_capacity_and_address_domains(self):
        data = tables()
        self.assertEqual(data['GemRecordOffsets'][1], list(range(0, 1345, 21)))
        for factor in (2, 3):
            limits = data[f'GemRowLimit{factor}'][1]
            costs = data[f'GemWork{factor}'][1]
            self.assertEqual(len(limits), 512)
            self.assertEqual(len(costs), 8192)
            for width, limit in enumerate(limits, 1):
                self.assertLessEqual(width*factor*limit, 8192)
                self.assertTrue(limit == 16 or width*factor*(limit+1) > 8192)
                for rows in range(1, 17):
                    index = ((rows-1) << 9) | (width-1)
                    self.assertEqual(costs[index], sum([width*factor]*rows))
                    self.assertLessEqual(costs[index]+8192, 65535)
        for stride in (320, 640, 1024, 1280):
            offsets = data[f'GemStep{stride}'][1]
            self.assertEqual(offsets[0], 0)
            self.assertEqual([b-a for a, b in zip(offsets, offsets[1:])], [stride]*16)
        for cost in (96, 120):
            for remaining in range(8193):
                count=data[f'GemGlyphCapacity{cost}'][1][remaining>>3]
                self.assertLessEqual(count*cost, remaining)
                self.assertTrue(count==64 or (count+1)*cost>remaining)
        self.assertEqual(data['GemScreenRows'][1][240], 76800)

    def test_reproducible_upper_memory_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'tables.h'
            first = generate(p)
            self.assertEqual(generate(p), first)
            self.assertEqual(first['payload_bytes'], 37132)
            self.assertIn('static const ULONG GemScreenRows[256]', p.read_text())


if __name__ == '__main__':
    unittest.main()
