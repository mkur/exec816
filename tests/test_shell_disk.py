import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from make_shell_disk import make
from filesystem_audit import Audit
from mydos_fixtures import Image


class ShellDiskTests(unittest.TestCase):
    def test_binary_exact_and_text_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'files'
            (source/'C').mkdir(parents=True)
            binary = bytes(range(256))+b'\r\n\x00\x9b'
            (source/'C/HELLO').write_bytes(binary)
            (source/'TEXT.TXT').write_bytes(b'one\r\ntwo\r\n')
            path = Path(directory)/'disk.atr'
            for size in (128,256):
                expected = make(path, source, binary_names={'C/HELLO'}, sector_bytes=size)
                image = Image(path.read_bytes())
                actual = {e['path']: image.file(e)[0] for e in image.walk() if not e['flags'] & 16}
                self.assertEqual((image.size,image.count),(size,720))
                self.assertEqual(actual, expected)
                self.assertEqual(actual['C/HELLO'], binary)
                self.assertEqual(actual['TEXT.TXT'], b'one\ntwo\n')

    def test_files_allocation_and_small_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'playground.atr'
            expected = make(path)
            image = Image(path.read_bytes())
            self.assertEqual((image.count, image.size, path.stat().st_size), (720, 128, 92176))
            self.assertEqual(set(expected), {'README.TXT', 'HELLO.TXT', 'C/README.TXT', 'S/STARTUP', 'S/USER', 'DOCS/COMMANDS.TXT', 'TOOLS/SUB/NOTE.TXT'})
            # Include the two short S: examples in the small data playground.
            self.assertLess(sum(map(len, expected.values())), 1536)
            used = {0, 1, 2, 3, 360, *range(361, 369), 720}
            found = {}
            for entry in image.walk():
                if entry['flags'] & 16:
                    chain = list(range(entry['start'], entry['start']+8))
                else:
                    payload, chain = image.file(entry)
                    found[entry['path']] = payload
                self.assertFalse(used.intersection(chain), entry['path'])
                used.update(chain)
            self.assertEqual(found, expected)
            vtoc = image.sector(360)
            free = {s for s in range(721) if vtoc[10+s//8] & (0x80 >> (s & 7))}
            self.assertEqual(free, set(range(721))-used)
            self.assertEqual(struct.unpack('<HH', vtoc[1:5]), (707, len(free)))

    def test_large_mydos_disk_uses_full_sector_links(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'files'
            source.mkdir()
            payload = bytes(range(256))*600
            (source/'LARGE.BIN').write_bytes(payload)
            path = Path(directory)/'system.atr'
            make(path, source, binary_names={'LARGE.BIN'}, sectors=5760)
            image = Image(path.read_bytes())
            entries = [entry for entry in image.walk() if entry['path'] == 'LARGE.BIN']
            self.assertEqual(len(entries), 1)
            actual, chain = image.file(entries[0])
            self.assertEqual(actual, payload)
            self.assertEqual(entries[0]['flags'], 0x46)
            self.assertGreater(max(chain), 1023)
            self.assertEqual(Audit(path.read_bytes()).mydos()['sectors'], 5760)


if __name__ == '__main__':
    unittest.main()
