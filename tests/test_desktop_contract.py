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
        self.assertNotIn('Request',sizes)
        self.assertNotIn('Content',sizes)
        self.assertNotIn('ClientRecord',sizes)
        constants = generate_desktop.ABI['constants']
        self.assertLessEqual(constants['WINDOWS'], 8)  # durable notice bits

    def test_library_calls_are_not_task_entries(self):
        self.assertFalse(application_entry({'name': 'M_DESKMENUCACHE_PUMP'}))
        self.assertFalse(application_entry({'name': 'M_LAYERCACHE_INIT'}))
        for module in ('DESKCORE','DESKMOVE','DESKCACHE','DESKSTATE','DESKPAINT','DESKINPUT','DESKDRAG','DESKHOST','DESKBOOT','DESKMENURENDER'):
            self.assertFalse(application_entry({'name': 'M_' + module + '_INIT'}))
        for module in ('AESCORE', 'AESHOST', 'AESBOOT', 'AESSTATE', 'AESTYPES', 'AESLOCKS', 'AESGUI', 'AESWINDOW', 'AESWINDOWSTATE', 'AESSNAPSHOT', 'AESDEFER', 'AESMOUSE'):
            self.assertFalse(application_entry({'name': 'M_' + module + '_INIT'}))

    def test_aes_protocol_is_generated(self):
        import generate_aes_server, generate_vdi_client
        for generator in (generate_aes_server, generate_vdi_client):
            for path, expected in generator.files().items():
                self.assertEqual(path.read_text(), expected)

    def test_hybrid_rpc_profile_excludes_message_and_event_opcodes(self):
        import generate_aes_server as aes
        self.assertEqual(aes.ABI['rpc_operations'], ['OP_INIT', 'OP_EXIT', 'OP_DISPLAY', 'OP_MOUSE_PROFILE', 'OP_MENU', 'OP_DRAG_OUTLINE'])
        self.assertEqual(aes.layout()['Request']['size'], 340)
        self.assertNotIn('words', aes.layout()['Request']['fields'])
        self.assertEqual(aes.layout()['Delivery']['size'], 32)
        self.assertEqual(aes.layout()['GuiDelivery']['size'], 40)
        self.assertEqual(aes.ABI['constants']['QUEUE_DEPTH'], 16)
        self.assertEqual(aes.ABI['constants']['RPC_INTIN_WORDS'], 6)
        self.assertEqual(aes.ABI['constants']['INTIN_WORDS'], 16)
