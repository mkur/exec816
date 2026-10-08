"""Cartridge images preserve XEX initialization order, bytes and boot variants."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_cartridge as cart


def segment(address, payload):
    return struct.pack('<HH', address, address+len(payload)-1)+payload


class CartridgePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        # Cross physical cartridge bank boundaries, with an INITAD followed by
        # another load to the same staging address; neither may be flattened.
        cls.raw = (b'\xff\xff'+segment(0x2000, bytes(range(256))*35)+
                   segment(0x02e2, b'\x00\x20')+b'\xff\xff'+
                   segment(0x2000, b'\x60')+segment(0x02e0, b'\x00\x20'))
        cls.xex = cls.root/'Exec-of816.xex'
        cls.xex.write_bytes(cls.raw)
        cls.record = cart.build(cls.xex, cls.root/'build')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_headers_checksums_and_both_power_on_banks(self):
        rom = (self.root/'build/Exec-of816-atarimax-8mbit.bin').read_bytes()
        self.assertEqual(len(rom), 1024*1024)
        self.assertEqual(rom[:8192], rom[-8192:])
        start, present, flags, init = struct.unpack_from('<HBBH', rom, 0x1ffa)
        self.assertEqual((start, present, flags, init),
                         (self.record['labels']['cart_start'], 0, 4,
                          self.record['labels']['cart_init']))
        for variant, kind in (('old',42), ('new',75)):
            data = (self.root/f'build/Exec-of816-atarimax-8mbit-{variant}.car').read_bytes()
            self.assertEqual(struct.unpack('>4sIII', data[:16]),
                             (b'CART',kind,sum(rom)&0xffffffff,0))
            self.assertEqual(data[16:],rom)

    def test_exact_xex_and_callback_order_survive_bank_boundaries(self):
        rom = (self.root/'build/Exec-of816-atarimax-8mbit.bin').read_bytes()
        embedded = rom[8192:8192+len(self.raw)]
        self.assertEqual(embedded, self.raw)
        self.assertEqual([a for a,_ in cart.segments(embedded)], [0x2000,0x2e2,0x2000,0x2e0])
        self.assertEqual(self.record['segments'],4)
        self.assertEqual(self.record['init_callbacks'],1)

    def test_reject_truncation_unsafe_destinations_and_missing_entry(self):
        for bad in (self.raw[:-1], b'\xff\xff'+segment(0x2000,b'\x60'),
                    b'\xff\xff'+segment(0x9000,b'x'),
                    b'\xff\xff'+segment(0xa000,b'x'),
                    b'\xff\xff'+segment(0x0400,b'x'),
                    b'\xff\xff'+segment(0x0800,b'x')+segment(0x2e0,b'\x00\x20'),
                    b'\xff\xff'+segment(0x09ff,b'x')+segment(0x2e0,b'\x00\x20'),
                    b'\xff\xff'+segment(0x02e2,b'\xff\x09')+segment(0x2e0,b'\x00\x20'),
                    b'\xff\xff'+segment(0x2000,b'x')+segment(0x2e0,b'\xff\x09'),
                    b'\xff\xff'+segment(0x02e2,b'\x00\x90')+segment(0x2e0,b'\x00\x20')):
            with self.subTest(data=bad[:12]):
                with self.assertRaises(ValueError):cart.segments(bad)

    def test_demo_preserves_all_released_files_and_whitelists_outputs(self):
        original = {'Exec-of816.xex':self.raw, 'system.atr':b'unchanged disk',
                    'altirraos-816.rom':b'unchanged firmware', 'README.txt':b'original guide'}
        sums = ''.join(f'{cart.digest(data)}  {name}\n' for name,data in original.items()).encode()
        source = self.root/'source.zip'
        with zipfile.ZipFile(source,'w') as z:
            for name,data in {**original,'SHA256SUMS':sums}.items():
                z.writestr('exec816-demo/'+name,data)
        out = self.root/'augmented'
        cart.augment_demo(source,out,cart.digest(source.read_bytes()))
        with zipfile.ZipFile(out/'exec816-demo.zip') as z:
            files = {n.removeprefix('exec816-demo/'):z.read(n) for n in z.namelist()}
        for name,data in original.items():self.assertEqual(files[name],data)
        self.assertFalse(any(n.endswith(('.o','.lst','.json','.map')) for n in files))
        for line in files['SHA256SUMS'].decode().splitlines():
            sha,name = line.split('  ',1)
            self.assertEqual(cart.digest(files[name]),sha)
        with self.assertRaisesRegex(ValueError,'checksum'):
            cart.augment_demo(source,out,'0'*64)


if __name__ == '__main__':
    unittest.main()
