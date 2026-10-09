import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from boot_config import ABI, describe, files, reserve_settings, valid_blocks
from generate_memory import layout


class BootConfigTests(unittest.TestCase):
    def test_capacity_and_layout(self):
        for count in (0,16,32,64,128,256,512,1024,2048):
            self.assertTrue(valid_blocks(count))
        for count in (-1,1,15,17,4096,65536,True,512.0,'512'):
            self.assertFalse(valid_blocks(count))
        memory = layout()
        record = memory['boot_config']
        self.assertEqual(record['address'], memory['regions']['boot-state'][0]+128)
        self.assertEqual(record['cache_blocks'], 512)
        self.assertEqual(ABI['size'], 8)
        self.assertEqual(ABI['fields']['flags'],7)
        self.assertEqual(ABI['default_flags'],ABI['flags']['VERBOSE'])
        self.assertIn('B_FIELD_CACHE_BLOCKS = $4', files(record)['boot-config.inc'])
        before = memory['profile']['code_origin']
        regions = dict(memory['regions'])
        reserve_settings(memory)
        self.assertEqual(memory['regions'], regions)
        self.assertEqual(memory['profile']['code_origin'], before+4)
        self.assertGreaterEqual(record['settings'], 65536)

    def test_build_default_and_overlap(self):
        memory = layout()
        memory['config']['cache_blocks'] = 0
        self.assertEqual(describe(memory)['cache_blocks'], 0)
        memory['config']['cache_blocks'] = 33
        with self.assertRaises(ValueError): describe(memory)
        memory['config']['cache_blocks'] = 512
        memory['regions']['boot-state'][1] = memory['regions']['boot-state'][0]+132
        with self.assertRaises(ValueError): describe(memory)


if __name__ == '__main__':
    unittest.main()
