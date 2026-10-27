import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_build_info import boot_identity, generate
from generate_boot_diagnostics import ABI, files


def identity_lines(assembly):
    lines = []
    for line in assembly.splitlines():
        if line.startswith('    .byte '):
            raw = bytes(map(int, line.removeprefix('    .byte ').split(',')))
            assert raw[-1] == 0
            lines.append(raw[:-1].decode('ascii'))
    return lines


class BootIdentityTests(unittest.TestCase):
    def test_shared_captured_identity(self):
        for display in ('v0.2.2', '1234567-clean', '1234567-dirty'):
            with self.subTest(display=display), tempfile.TemporaryDirectory() as directory:
                captured = dict(revision='1234567'+'0'*33, dirty=display.endswith('dirty'),
                                display=display, tag=display if display.startswith('v') else None)
                with patch('generate_build_info.identity', return_value=captured) as read_identity:
                    record = generate(directory, (), 12)
                self.assertEqual(read_identity.call_count, 1)
                saved = json.loads((Path(directory)/'exec-build.json').read_text())
                self.assertEqual(saved, record)
                title = record['strings']['banner'].strip()
                self.assertEqual(identity_lines((Path(directory)/'boot-build.inc').read_text()), [title])
                self.assertIn(title, record['strings']['version'])

    def test_long_identity_fits_os_lines_without_losing_content(self):
        record = dict(version='12.34.567890123456789', display='1234567-dirty')
        lines = identity_lines(boot_identity(record))
        self.assertTrue(all(len(line) <= 39 for line in lines))
        self.assertEqual(' '.join(lines), f"Exec816 {record['version']} ({record['display']})")

    def test_existing_event_numbers_and_failure_range_are_preserved(self):
        names = [name for name, _ in ABI['events']]
        self.assertEqual(names.index('READY'), 11)
        self.assertEqual(names.index('WORKER'), 22)
        self.assertEqual((ABI['failure_first'], ABI['failure_last']), (14, 20))
        self.assertTrue(all(names.index(name) > ABI['failure_last'] for name in
                            ('IDENTITY', 'ROM_CRC', 'ROM_PROFILE', 'SDX_ROM')))
        for path, text in files().items():
            self.assertEqual(path.read_text(), text)


if __name__ == '__main__':
    unittest.main()
