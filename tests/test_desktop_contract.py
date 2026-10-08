"""Desktop ABI consistency; behavior is covered by the emitted service fixture."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import generate_desktop
from generate_tasks import application_entry


class DesktopContractTests(unittest.TestCase):
    def test_generated_layout_and_unique_symbols(self):
        for path, expected in generate_desktop.files().items():
            self.assertEqual(path.read_text(), expected)
            constants = [line.split('=')[0] for line in expected.splitlines()
                         if line.startswith('PUBLIC CONST ')]
            self.assertEqual(len(constants), len(set(constants)))
        sizes = {name: value['size'] for name, value in generate_desktop.layout().items()}
        self.assertEqual(sizes['Request'], 92)
        self.assertEqual(sizes['Service'], 14186)
        self.assertEqual(generate_desktop.layout()['Request']['fields']['message'], 0)
        constants = generate_desktop.ABI['constants']
        self.assertEqual(constants['EVENTS'] & (constants['EVENTS'] - 1), 0)
        self.assertLessEqual(constants['WINDOWS'], 8)  # durable notice bits

    def test_library_calls_are_not_task_entries(self):
        for module in ('DESKTOP', 'DESKCORE', 'DESKMOVE', 'DESKCACHE', 'DESKEVENTS', 'DESKSTATE', 'DESKPAINT', 'DESKINPUT', 'DESKDRAG', 'DESKHOST', 'DESKBOOT', 'DESKWIDGETS', 'DESKWIDGETINPUT'):
            self.assertFalse(application_entry({'name': 'M_' + module + '_INIT'}))
        for module in ('AESCORE', 'AESHOST', 'AESBOOT', 'AESSTATE', 'AESTYPES', 'AESLOCKS', 'AESGUI', 'AESWINDOW', 'AESWINDOWSTATE'):
            self.assertFalse(application_entry({'name': 'M_' + module + '_INIT'}))

    def test_aes_protocol_is_generated(self):
        import generate_aes_server, generate_vdi_client
        for generator in (generate_aes_server, generate_vdi_client):
            for path, expected in generator.files().items():
                self.assertEqual(path.read_text(), expected)

    def test_hybrid_rpc_profile_excludes_message_and_event_opcodes(self):
        import generate_aes_server as aes
        self.assertEqual(aes.ABI['rpc_operations'], ['OP_INIT', 'OP_EXIT', 'OP_UPDATE', 'OP_CREATE', 'OP_OPEN', 'OP_CLOSE', 'OP_DELETE', 'OP_SET', 'OP_DISPLAY', 'OP_MOUSE_PROFILE'])
        self.assertEqual(aes.layout()['Request']['size'], 112)
        self.assertNotIn('words', aes.layout()['Request']['fields'])
        self.assertEqual(aes.layout()['Delivery']['size'], 32)
        self.assertEqual(aes.layout()['GuiDelivery']['size'], 36)
        self.assertEqual(aes.ABI['constants']['QUEUE_DEPTH'], 16)
        self.assertEqual(aes.ABI['constants']['RPC_INTIN_WORDS'], 6)
        self.assertEqual(aes.ABI['constants']['INTIN_WORDS'], 16)

    def test_demo_registers_only_its_worker_entry(self):
        self.assertTrue(application_entry({'name': 'M_DESKAPP_RUN_123ABC'}))
        for routine in ('STOP', 'RETIRE', 'REPLACE', 'CANCELWAIT'):
            self.assertFalse(application_entry({'name': 'M_DESKAPP_' + routine + '_123ABC'}))
