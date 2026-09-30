"""Library layout, copied INCLUDE ownership and retained evidence path handling."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from library_paths import SUBSYSTEMS, library_file, module_args, read_source, record_input_paths


class LibraryPathsTests(unittest.TestCase):
    def test_search_paths_and_unique_modules(self):
        self.assertEqual(set(p.name for p in (ROOT/'lib').iterdir() if p.is_dir()), set(SUBSYSTEMS))
        self.assertEqual(list((ROOT/'lib').glob('*.act')), [])
        self.assertEqual(list((ROOT/'lib').glob('*.inc')), [])
        self.assertEqual(module_args(), [arg for group in SUBSYSTEMS
                                        for arg in ('--module-path', ROOT/'lib'/group)])
        files = list((ROOT/'lib').rglob('*.act'))+list((ROOT/'lib').rglob('*.inc'))
        for path in files:
            self.assertEqual(library_file(path.name), path)

    def test_missing_and_duplicate_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with self.assertRaises(RuntimeError):
                library_file('example.act', root)
            for group in ('exec', 'dos'):
                path = root/'lib'/group/'example.act'
                path.parent.mkdir(parents=True)
                path.write_text('MODULE EXAMPLE\nENDMODULE\n')
            with self.assertRaises(RuntimeError):
                library_file('example.act', root)
            with self.assertRaises(ValueError):
                library_file('../example.act', root)

    def test_copied_sources_preserve_include_owners_and_generated_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root/'exec'/'policy.act'
            source.parent.mkdir()
            types = root/'dos'/'types.inc'
            types.parent.mkdir()
            types.write_text('CONST VALUE=1\n')
            override = root/'output'/'types.inc'
            body = ('MODULE POLICY\n  INCLUDE "../dos/types.inc" ; shared\n'
                    'INCLUDE "generated.inc"\nENDMODULE\n')
            for newline in ('\n', '\r\n'):
                with self.subTest(newline=repr(newline)):
                    source.write_bytes(body.replace('\n', newline).encode())
                    self.assertEqual(read_source(source), body.replace('../dos/types.inc', str(types)))
                    self.assertEqual(read_source(source, {'types.inc': override}),
                                     body.replace('../dos/types.inc', str(override)))
            # Already relocated sources, including absolute paths, can be instrumented again.
            relocated = root/'copy.act'
            relocated.write_text(read_source(source))
            self.assertEqual(read_source(relocated), read_source(source))

    def test_historical_paths_are_copied_without_changing_hashes(self):
        record = {'inputs': {'lib/siodriver.act': 'original'},
                  'cases': [{'build': {'task_inputs': {'lib/siodriver.act': 'different'}}}]}
        original = copy.deepcopy(record)
        current = record_input_paths(record)
        self.assertEqual(record, original)
        self.assertEqual(current['inputs'], {'lib/io/siodriver.act': 'original'})
        self.assertEqual(current['cases'][0]['build']['task_inputs'], {'lib/io/siodriver.act': 'different'})
        self.assertEqual(record_input_paths(current), current)
        record['inputs']['lib/io/siodriver.act'] = 'original'
        with self.assertRaises(RuntimeError):
            record_input_paths(record)


if __name__ == '__main__':
    unittest.main()
