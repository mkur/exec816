import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_st_reference import extract_workload, parse_report, SOURCE


def report():
    lines = ['AES id=0 screen=640,400 colours=2 font=7,6,8,8 clock=200 magic=1']
    for kind, count in enumerate((5, 33, 9)):
        for sample in range(10):
            lines.append(f'case={kind} sample={sample} count={count} visible=1 okay=1 '
                f'ticks={100 if sample<2 else 8} work=33,43,478,164')
    return '\r\n'.join(lines)+'\r\n'


class STReferenceTests(unittest.TestCase):
    def test_report_discards_warmups_and_preserves_all_observations(self):
        result = parse_report(report())
        self.assertEqual(result['timing_resolution_ms'], 5)
        self.assertEqual([case['elapsed_ms_median'] for case in result['cases']], [40]*3)
        self.assertEqual(result['cases'][0]['ticks'], [100, 100]+[8]*8)

    def test_rejects_incomplete_failed_repeated_and_incompatible_runs(self):
        original = report()
        mutations = [original.rsplit('case=2 sample=9', 1)[0],
            original.replace('okay=1', 'okay=0', 1),
            original.replace('sample=9', 'sample=8', 1),
            original.replace('count=33', 'count=32', 1),
            original.replace('visible=1', 'visible=0', 1),
            original.replace('colours=2', 'colours=16'),
            original.replace('478,164', '478,120', 1),
            original.replace('work=33,43', 'work=34,43', 1)]
        for mutated in mutations:
            with self.subTest(mutated=mutated[:100]), self.assertRaises(ValueError):
                parse_report(mutated)

    def test_failed_magic_boot_cannot_be_reported_as_magic_evidence(self):
        with self.assertRaisesRegex(ValueError, 'MagiC cookie'):
            parse_report(report().replace('magic=1', 'magic=0'), expected_magic=True)
        with self.assertRaisesRegex(ValueError, 'MagiC cookie'):
            parse_report(report(), expected_magic=False)
        self.assertTrue(parse_report(report(), expected_magic=True)['magic_cookie'])

    def test_workload_keeps_exact_native_functions_after_newline_normalization(self):
        native = SOURCE.read_text()
        with TemporaryDirectory() as directory:
            path = Path(directory)/'baseline.c'
            path.write_bytes(native.replace('\n', '\r\n').encode())
            extracted = extract_workload(path.read_text())
        self.assertEqual(extracted, extract_workload(native))
        for function in extracted.strip().split('\n\n'):
            self.assertIn(function, native)
        self.assertEqual(extracted.count('\nstatic '), 2)

    def test_missing_or_duplicate_native_function_cannot_build_another_workload(self):
        native = SOURCE.read_text()
        with self.assertRaises(ValueError):
            extract_workload(native.replace('static WORD draw_objects(', 'static WORD missing('))
        with self.assertRaises(ValueError):
            extract_workload(native+'\n'+extract_workload(native))


if __name__ == '__main__':
    unittest.main()
