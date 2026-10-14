"""Protocol admission boundaries and generated/source provenance."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from generate_fujinet import ABI, constants


class FujiProtocolTests(unittest.TestCase):
    def test_wire_shapes(self):
        c = constants()
        self.assertEqual((c['CONTROL_UNIT'], c['CMD_SET_PATH'], c['CMD_EJECT']),
                         (0x70, 0xe2, 0xe9))
        self.assertEqual((c['HOST_TABLE_BYTES'], c['DISK_TABLE_BYTES'],
                          c['ADAPTER_BYTES'], c['PATH_BYTES']), (256, 304, 140, 256))
        self.assertEqual((c['MODE_READ'], c['MODE_WRITE'], c['MODE_MOUNTED']),
                         (1, 2, 0x40))

    def test_malformed_shapes(self):
        for field in ('HOST_TABLE_BYTES', 'DISK_TABLE_BYTES', 'DISK_FILE',
                      'ADAPTER_VERSION'):
            candidate = copy.deepcopy(ABI)
            candidate['constants'][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                constants(candidate)

    def test_command_collision(self):
        candidate = copy.deepcopy(ABI)
        candidate['constants']['CMD_EJECT'] = candidate['constants']['CMD_ATTACH']
        with self.assertRaises(ValueError):
            constants(candidate)

    def test_provenance_is_immutable_and_explicit(self):
        pin = json.loads((ROOT / 'toolchain/fujinet-control.json').read_text())
        self.assertEqual(pin['execution']['kind'], 'Altirra scripted SIO peer')
        self.assertFalse(pin['execution']['physical_qualification'])
        for source in pin['sources']:
            self.assertRegex(source['revision'], r'^[0-9a-f]{40}$')
            for file in source['files']:
                self.assertIn(source['revision'], file['url'])
                self.assertRegex(file['sha256'], r'^[0-9a-f]{64}$')
