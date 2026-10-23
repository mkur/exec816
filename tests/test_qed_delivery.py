"""Incomplete rights/scope must not become a supported-distribution claim."""
import json
import tempfile
import sys
import unittest
from unittest.mock import patch
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


class BuildSelectionTests(unittest.TestCase):
    def test_incompatible_qed_selection_fails_before_compiler(self):
        from build_demo import bundle
        for selection in ({}, dict(gem_desktop=True, filesystem='mydos'),
                          dict(gem_desktop=True, sector_bytes=128),
                          dict(gem_desktop=True, system_kib=360)):
            with self.subTest(selection=selection), patch('build_demo.compiler') as compiler:
                with self.assertRaisesRegex(RuntimeError, 'QED requires'):
                    bundle(Path('/unused'), Path('/unused'), qed=True, **selection)
                compiler.assert_not_called()


class ProviderAndPatchTests(unittest.TestCase):
    def inputs(self):
        from qed_delivery import PORT, sha256
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        directory=Path(temp.name).resolve();(directory/'program.app').write_bytes(b'APP')
        layout=dict(status='executable-development',complete_link=True,abi=ABI,
            image=dict(provenance=dict(analysis_only=False,tools={},runtime=dict(path='/runtime',sha256='0'))),
            app=dict(sha256='0'),build_inputs={},resident_provider=dict(path='/original',sha256='0'))
        sources=dict(patches={p.name:sha256(p) for p in (PORT/'patches').glob('*.patch')},
            source_manifest_sha256=sha256(PORT/'inputs.json'),native_inputs={})
        resource=dict(resource_sha256='0',header_sha256='0',selection_sha256='0',generator_sha256='0')
        provider=dict(segments=[],zero_fill=[],provenance=dict(readonly_table_banks=[]),
            symbols={name:0 for name in ABI['imports']})
        current=json.loads(json.dumps(provider));current['symbols'][next(iter(ABI['imports']))]=1
        values={directory/'layout.json':layout,directory/'inputs/sources.json':sources,
                directory/'inputs/resource/resource.json':resource,Path('/original'):provider,
                Path('/current'):current}
        return directory,values

    def test_changed_patch_ledger_rejects_packaging(self):
        directory,values=self.inputs();values[directory/'inputs/sources.json']['patches']={}
        with patch('qed_delivery.read',side_effect=values.__getitem__), patch('qed_delivery.checked'), \
             patch('qed_delivery.reject_analysis'):
            with self.assertRaisesRegex(RuntimeError,'Changed QED source patch set'):
                production(directory,Path('/current'))

    def test_mismatched_provider_rejects_packaging(self):
        directory,values=self.inputs()
        with patch('qed_delivery.read',side_effect=values.__getitem__), patch('qed_delivery.checked'), \
             patch('qed_delivery.reject_analysis'):
            with self.assertRaisesRegex(RuntimeError,'provider identity differs'):
                production(directory,Path('/current'))
