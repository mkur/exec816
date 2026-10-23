"""Incomplete rights/scope must not become a supported-distribution claim."""
import json
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from qed_delivery import REQUIREMENTS, checked, production, require_distribution
from c_program import ABI


class DeliveryGateTests(unittest.TestCase):
    def complete(self):
        return dict(unresolved=[], requirements={key: {'status': 'pass'} for key in REQUIREMENTS})

    def test_unresolved_grant_rejects_complete_functional_results(self):
        record = self.complete();record['unresolved'] = ['native-adapter-grant']
        with self.assertRaisesRegex(RuntimeError, 'Unresolved QED grants'):
            require_distribution(record)

    def test_missing_requirement_is_not_a_pass(self):
        record = self.complete();record['requirements'].pop('launch')
        with self.assertRaisesRegex(RuntimeError, 'Incomplete QED delivery'):
            require_distribution(record)

    def test_pending_requirement_is_not_a_pass(self):
        record = self.complete();record['requirements']['files']['status'] = 'pending'
        with self.assertRaisesRegex(RuntimeError, 'Incomplete QED delivery'):
            require_distribution(record)

    def test_complete_gate(self):
        require_distribution(self.complete())


class ProductionInputTests(unittest.TestCase):
    def test_changed_or_missing_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/'input'
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'Changed QED input'):
                checked(source, '0'*64)
            source.unlink()
            with self.assertRaisesRegex(RuntimeError, 'Changed QED input'):
                checked(source, '0'*64)

    def test_fixture_and_analysis_builds_are_rejected_before_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            layout = dict(status='executable-development', complete_link=True, abi=ABI,
                image=dict(provenance=dict(analysis_only=False)),
                build_inputs={'/repo/tests/programs/qed_fixture.c': 'hash'})
            (directory/'layout.json').write_text(json.dumps(layout))
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                production(directory, directory/'unused-provider.json')
            layout['build_inputs'] = {}
            layout['image']['provenance']['analysis_only'] = True
            (directory/'layout.json').write_text(json.dumps(layout))
            with self.assertRaisesRegex(RuntimeError, 'current executable production'):
                production(directory, directory/'unused-provider.json')
