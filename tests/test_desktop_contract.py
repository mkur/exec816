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
        self.assertEqual(sizes['Service'], 12280)
        self.assertEqual(generate_desktop.layout()['Request']['fields']['message'], 0)
        constants = generate_desktop.ABI['constants']
        self.assertEqual(constants['EVENTS'] & (constants['EVENTS'] - 1), 0)
        self.assertLessEqual(constants['WINDOWS'], 8)  # durable notice bits

    def test_library_calls_are_not_task_entries(self):
        for module in ('DESKTOP', 'DESKCORE', 'DESKEVENTS', 'DESKSTATE', 'DESKPAINT', 'DESKINPUT', 'DESKDRAG', 'DESKHOST', 'DESKBOOT', 'DESKWIDGETS', 'DESKWIDGETINPUT'):
            self.assertFalse(application_entry({'name': 'M_' + module + '_INIT'}))

    def test_demo_registers_only_its_worker_entry(self):
        self.assertTrue(application_entry({'name': 'M_DESKAPP_RUN_123ABC'}))
        for routine in ('STOP', 'RETIRE', 'REPLACE', 'CANCELWAIT'):
            self.assertFalse(application_entry({'name': 'M_DESKAPP_' + routine + '_123ABC'}))
