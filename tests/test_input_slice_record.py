import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import record_input_slice as recorder


class InputEvidenceTests(unittest.TestCase):
    def fixture(self, root):
        folder = root/'run'
        folder.mkdir()
        report = dict(status='pass', cases=[dict(name='control', status='pass')],
                      build=dict(platform_inputs={}, task_inputs={}))
        (folder/'results.json').write_text(json.dumps(report))
        (root/'source.c').write_text('old source\n')
        (folder/'c-image.json').write_text(json.dumps(dict(provenance=dict(
            source_inputs={'source.c': recorder.sha256(root/'source.c')}))))
        return folder, report

    def test_rejects_partial_and_failed_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, report = self.fixture(Path(tmp))
            for status, cases in [('running', report['cases']), ('fail', report['cases']),
                                  ('pass', []), ('pass', [dict(status='fail')])]:
                report.update(status=status, cases=cases)
                (folder/'results.json').write_text(json.dumps(report))
                with self.subTest(status=status, cases=cases), self.assertRaises(RuntimeError):
                    recorder.read_run(folder)

    def test_rejects_changed_source_before_publishing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, _ = self.fixture(root)
            (root/'source.c').write_text('changed source\n')
            with patch.object(recorder, 'ROOT', root), self.assertRaisesRegex(RuntimeError, 'Stale source'):
                recorder.read_run(folder)

    def test_rejects_changed_tested_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, report = self.fixture(root)
            (folder/'program').mkdir()
            (folder/'program/program.xex').write_bytes(b'old binary')
            report['xex_sha256'] = recorder.sha256(folder/'program/program.xex')
            (folder/'results.json').write_text(json.dumps(report))
            (folder/'program/program.xex').write_bytes(b'changed binary')
            with patch.object(recorder, 'ROOT', root), self.assertRaisesRegex(RuntimeError, 'Changed tested XEX'):
                recorder.read_run(folder)
