"""Fail closed when a GEM source, platform identity or interface layout drifts."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import gem_vdi_inputs
from native_program import verify_machine
from os_boundary import ROOT, settings

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())


class Machine:
    def __init__(self, pin):
        self.pin = copy.deepcopy(pin)
        self.config_values = dict(machine='800XL', memory='64K', video='pal', basic=False,
                                  highbanks=63, addons='custom', **pin['startup_configuration'])
        self.core = b'\x10\x26'
        self.extra = []

    def config(self):
        return self.config_values

    def device_list(self):
        return dict(installed=[dict(tag='vbxe', internal=False)]+self.extra)

    def device_get(self, tag):
        return dict(present=True, settings=self.pin['devices'][0]['settings'])

    def regs(self):
        return dict(mode='65C816', clock_multiplier=8, shadow_rom=True)

    def memdump(self, address, size):
        return self.core if address == 0xd640 else bytes(size)


class GemInputTests(unittest.TestCase):
    def test_source_verification_preserves_changed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source = directory/'src/vdi.c'
            source.parent.mkdir()
            source.write_bytes(b'original\r\n')
            manifest = directory/'manifest.json'
            manifest.write_text(json.dumps(dict(files={'src/vdi.c': dict(
                role='extract', sha256=hashlib.sha256(source.read_bytes()).hexdigest())})))
            with patch.object(gem_vdi_inputs, 'MANIFEST', manifest):
                gem_vdi_inputs.source_inputs(directory)
                source.write_bytes(b'changed\n')
                with self.assertRaisesRegex(RuntimeError, 'Changed GEM input'):
                    gem_vdi_inputs.source_inputs(directory, fetch=True)
                self.assertEqual(source.read_bytes(), b'changed\n')
                source.unlink()
                with self.assertRaisesRegex(RuntimeError, 'Missing GEM input'):
                    gem_vdi_inputs.source_inputs(directory)

    def test_pin_does_not_change_default_settings(self):
        base = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        rom = ROOT/'build/firmware/altirraos-816.rom'
        self.assertEqual(settings(rom, base), settings(rom, PIN))
        self.assertNotIn('devices', base)
        manifest = json.loads(gem_vdi_inputs.MANIFEST.read_text())
        self.assertEqual(manifest['platform_pin_sha256'], gem_vdi_inputs.sha256(ROOT/manifest['platform_pin']))

    def test_download_must_match_before_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            manifest = directory/'manifest.json'
            manifest.write_text(json.dumps(dict(revision='a'*40, files={'source.c': dict(
                role='extract', sha256=hashlib.sha256(b'expected').hexdigest())})))
            with patch.object(gem_vdi_inputs, 'MANIFEST', manifest):
                with patch('urllib.request.urlopen', return_value=io.BytesIO(b'changed')):
                    with self.assertRaisesRegex(RuntimeError, 'Downloaded GEM source differs'):
                        gem_vdi_inputs.source_inputs(directory, fetch=True)
                self.assertFalse((directory/'source.c').exists())
                with patch('urllib.request.urlopen', return_value=io.BytesIO(b'expected')):
                    gem_vdi_inputs.source_inputs(directory, fetch=True)
                self.assertEqual((directory/'source.c').read_bytes(), b'expected')

    def test_exact_device_and_cpu_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            rom = Path(folder)/'rom'
            rom.write_bytes(bytes(16384))
            bridge = Machine(PIN)
            verify_machine(bridge, rom, PIN)
            mutations = (
                lambda b: b.pin['devices'][0]['settings'].update(version=124),
                lambda b: b.pin['devices'][0]['settings'].update(alt_page=True),
                lambda b: b.pin['devices'][0]['settings'].update(shared_mem=True),
                lambda b: setattr(b, 'core', b'\x10\x24'),
                lambda b: b.extra.append(dict(tag='covox', internal=False)),
                lambda b: b.config_values.update(siopatch='on'),
                lambda b: b.config_values.update(highbanks=15),
                lambda b: setattr(b, 'regs', lambda: dict(mode='6502', clock_multiplier=8, shadow_rom=True)),
            )
            for mutate in mutations:
                bridge = Machine(PIN)
                mutate(bridge)
                with self.subTest(mutation=mutate), self.assertRaises(RuntimeError):
                    verify_machine(bridge, rom, PIN)
            default = copy.deepcopy(PIN)
            default.pop('devices')
            default['machine'].pop('addons')
            with self.assertRaisesRegex(RuntimeError, 'addons'):
                verify_machine(Machine(PIN), rom, default)

    def test_service_layout_extents_and_opcode_identity(self):
        abi = json.loads((ROOT/'abi/gem-vdi.json').read_text())
        for record in abi['records'].values():
            cursor = 0
            for name, kind, offset, size in record['fields']:
                self.assertEqual(offset, cursor, name)
                cursor += size
            self.assertEqual(cursor, record['size'])
        request = abi['records']['Request']
        ports = json.loads((ROOT/'abi/ports.json').read_text())
        self.assertEqual(request['fields'][0][3], ports['records']['Message']['size'])
        limits = abi['limits']
        self.assertEqual(request['size']+limits['payload_bytes'], limits['packet_bytes'])
        commands = {(op['opcode'], op['subopcode']):op for op in abi['vdi_operations']}
        self.assertEqual(len(commands), len(abi['vdi_operations']))
        self.assertEqual(commands[11,1]['name'], 'v_bar')
        self.assertNotIn((11,0), commands)
        self.assertNotIn((100,0), commands)
        for op in commands.values():
            self.assertIn(op['transport'], abi['services'])
            for field in ('point_pairs', 'int_words'):
                low, high = op[field]
                self.assertTrue(0 <= low <= high)


if __name__ == '__main__':
    unittest.main()
