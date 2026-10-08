"""Pixel observers must not identify windows through transient GEM outputs."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from gem_applications import scene_symbols
from generate_aes_server import layout


class Bridge:
    def __init__(self):
        self.memory = bytearray(65536)

    def memdump(self, address, count):
        return bytes(self.memory[address:address+count])

    def put(self, address, value, size):
        self.memory[address:address+size] = value.to_bytes(size, 'little')


class ApplicationObserverTests(unittest.TestCase):
    def test_published_view_identifies_task_with_cleared_work_outputs(self):
        bridge = Bridge()
        records = layout()
        request = records['Request']['fields']
        view = records['WindowView']['fields']
        # Two live copies of Counter; both caller work[] outputs are zero.
        apps = []
        for index, bounds in enumerate(((24, 48, 224, 144), (240, 48, 440, 144))):
            context, target, task = 256+index*512, 2048+index*1024, 12800+index*128
            bridge.put(64+index*4, context, 4)
            bridge.put(context+request['owner'], task, 3)
            bridge.put(context+request['view'], target, 3)
            bridge.put(target+view['shown'], 1, 2)
            for offset, value in enumerate(bounds):
                bridge.put(target+view['bounds']+offset*2, value, 2)
            apps.append(dict(name='counter', task=task, symbols={'GEMCounter': 16384+index*256}))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'c-image.json').write_text(json.dumps({'symbols': {'contexts': 64}}))
            with patch('gem_applications.instances', return_value=apps):
                self.assertEqual(scene_symbols(bridge, {}, directory, b'Counter',
                                               (240, 48, 440, 144)), apps[1]['symbols'])
                bridge.put(3072+view['shown'], 0, 2)
                with self.assertRaisesRegex(RuntimeError, 'No unique loaded window model'):
                    scene_symbols(bridge, {}, directory, b'Counter', (240, 48, 440, 144))


if __name__ == '__main__':
    unittest.main()
