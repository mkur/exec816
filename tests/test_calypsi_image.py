"""Check the C loader boundary without running a compiler or emulator."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from calypsi_image import check_layout, read_image
from generate_calypsi import files


def elf_image():
    blob = bytearray(888)
    blob[:16] = b'\x7fELF\x01\x01\x01'+bytes(9)
    struct.pack_into('<HHIIIIIHHHHHH', blob, 16, 2, 257, 1, 0xc0000,
                     52, 768, 0, 52, 32, 5, 40, 3, 0)
    segments = [(0, 0, 0, 128, 6), (272, 0x100, 16, 16, 4),
                (256, 0xc0000, 2, 65536, 5), (288, 0xd0000, 4, 4, 6),
                (0, 0xd0004, 0, 65532, 6)]
    for index, (offset, address, size, reserved, flags) in enumerate(segments):
        struct.pack_into('<IIIIIIII', blob, 52+32*index,
                         1, offset, address, address, size, reserved, flags, 1)
    blob[256:258] = b'\x6b\x6b'
    blob[288:292] = b'C816'
    struct.pack_into('<IIII', blob, 272, 0x31434345, 0xd0004, 10, 20)
    names = bytearray(b'\0')
    symbols = [('main', 0xc0000, 2), ('Receiver', 0xc0001, 2),
               ('_Dp', 0, 1), ('_Vfp', 16, 1),
               ('_DirectPageStart', 0, 0), ('_NearBaseAddress', 0, 0)]
    for index, (name, value, kind) in enumerate(symbols, 1):
        struct.pack_into('<IIIBBH', blob, 512+index*16, len(names), value, 0, kind, 0, 1)
        names.extend(name.encode()+b'\0')
    blob[320:320+len(names)] = names
    struct.pack_into('<IIIIIIIIII', blob, 808, 0, 3, 0, 0, 320, len(names), 0, 0, 1, 0)
    struct.pack_into('<IIIIIIIIII', blob, 848, 0, 2, 0, 0, 512, 112, 1, 0, 4, 16)
    return blob


class CalypsiImageTests(unittest.TestCase):
    def parse(self, blob, entries=('Receiver',)):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'c.elf'
            path.write_bytes(blob)
            return read_image(path, entries)

    def test_only_real_storage_is_loaded(self):
        image = self.parse(elf_image())
        self.assertEqual([(s['address'], bytes(s['bytes'])) for s in image['segments']],
                         [(0xc0000, b'\x6b\x6b'), (0xd0000, b'C816')])
        self.assertEqual(image['zero_fill'], [dict(address=0xd0004, size=10, writable=True)])
        self.assertEqual(image['task_entries'], [0xc0001])
        self.assertEqual(image['provenance']['dp_workspace_bytes'], 20)

    def test_rejects_wrong_memory_model_and_fixed_bank_zero(self):
        for offset, value, message in [(512+3*16+4, 0x80, 'runtime must use'),
                                        (272+12, 129, 'register allocation'),
                                        (52+3*32+8, 0x2800, 'Unsupported ELF'),
                                        (272+4, 0xe0000, 'BSS outside')]:
            with self.subTest(offset=offset):
                blob = elf_image()
                struct.pack_into('<I', blob, offset, value)
                with self.assertRaisesRegex(RuntimeError, message):
                    self.parse(blob)

    def test_rejects_non_function_or_unlinked_task_entry(self):
        blob = elf_image()
        blob[512+2*16+12] = 1
        with self.assertRaisesRegex(RuntimeError, 'not a linked function'):
            self.parse(blob)
        blob = elf_image()
        struct.pack_into('<I', blob, 512+2*16+4, 0xc0100)
        with self.assertRaisesRegex(RuntimeError, 'not a linked function'):
            self.parse(blob)
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            self.parse(elf_image(), ('Receiver', 'Receiver'))

    def test_extra_code_bank_and_actual_extents(self):
        blob = elf_image()
        struct.pack_into('<H', blob, 44, 6)
        struct.pack_into('<IIIIIIII', blob, 52+5*32,
                         1, 258, 0xe0000, 0xe0000, 2, 65536, 5, 1)
        blob[258:260] = b'\x6b\x6b'
        struct.pack_into('<I', blob, 512+2*16+4, 0xe0001)
        image = self.parse(blob)
        self.assertEqual(image['task_entries'], [0xe0001])
        struct.pack_into('<I', blob, 512+2*16+4, 0xe0002)
        with self.assertRaisesRegex(RuntimeError, 'not a linked function'):
            self.parse(blob)

    def test_rejects_code_bank_write_permission_and_overlap(self):
        blob = elf_image()
        struct.pack_into('<I', blob, 52+2*32+24, 7)
        with self.assertRaisesRegex(RuntimeError, 'upper-bank layout'):
            self.parse(blob)
        blob = elf_image()
        struct.pack_into('<H', blob, 44, 6)
        blob[52+5*32:52+6*32] = blob[52+2*32:52+3*32]
        with self.assertRaisesRegex(RuntimeError, 'Overlapping C storage'):
            self.parse(blob)

    def test_rejects_truncated_and_unresolved_images(self):
        for size in (0, 52, 887):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                self.parse(elf_image()[:size])
        blob = elf_image()
        struct.pack_into('<H', blob, 512+2*16+14, 0)
        with self.assertRaisesRegex(RuntimeError, 'Unresolved'):
            self.parse(blob)

    def test_emitted_layout_disagreement_fails_before_link(self):
        blob = bytearray(256)
        blob[:16] = b'\x7fELF\x01\x01\x01'+bytes(9)
        struct.pack_into('<HHIIIIIHHHHHH', blob, 16, 1, 257, 1, 0, 0, 52, 0, 52, 0, 0, 40, 3, 1)
        names = b'\0exec_layout\0'
        blob[200:200+len(names)] = names
        struct.pack_into('<IIIIIIIIII', blob, 92, 0, 3, 0, 0, 200, len(names), 0, 0, 1, 0)
        struct.pack_into('<IIIIIIIIII', blob, 132, 1, 1, 0, 0, 220, 4, 0, 0, 2, 0)
        struct.pack_into('<HH', blob, 220, 16, 14)
        checks = [('sizeof(struct Message)', 16), ('offsetof(struct Message, mn_Length)', 14)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'layout.o'
            path.write_bytes(blob)
            self.assertEqual(check_layout(path, checks), dict(checks))
            struct.pack_into('<H', blob, 222, 16)
            path.write_bytes(blob)
            with self.assertRaisesRegex(RuntimeError, r'mn_Length\) = 16, expected 14'):
                check_layout(path, checks)

    def test_generated_definitions_are_current(self):
        for path, content in files().items():
            self.assertEqual(path.read_text(), content, str(path))
