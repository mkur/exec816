import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_bootable_atr import ABI,Volume,build,check_layout
from filesystem_audit import Audit


class BootableATR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temporary.name)
        cls.source=cls.root/'source';cls.source.mkdir()
        (cls.source/'WORK').mkdir();(cls.source/'WORK/NOTE.TXT').write_bytes(b'Keep my work\n')
        # Repeated staged writes exceed 64 KiB without overwriting the reader.
        cls.xex=cls.root/'kernel.xex'
        segment=struct.pack('<HH',0x6200,0x62ff)+bytes(range(256))
        cls.xex.write_bytes(b'\xff\xff'+segment*300+struct.pack('<HHH',0x2e0,0x2e1,0x6200))
        cls.image=cls.root/'exec816.atr'
        cls.report=build(cls.image,cls.source,cls.xex,cls.root/'reader')

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_independent_allocation_and_exact_large_boot_file(self):
        audit=Audit(self.image.read_bytes());report=audit.sdfs()
        self.assertEqual(report['sectors'],8192)
        self.assertEqual(audit.files['EXEC816.XEX'],self.xex.read_bytes())
        self.assertEqual(audit.files['WORK/NOTE.TXT'],b'Keep my work\n')
        self.assertGreater(len(audit.files['EXEC816.XEX']),65536)
        self.assertGreater(report['free'],7000)

    def test_locator_points_to_allocated_protected_reader(self):
        volume=Volume(self.image.read_bytes());raw=volume.image.sector(1)
        at=ABI['locator_offset']
        magic,first,count,address,entry=struct.unpack_from('<4sHHHH',raw,at)
        self.assertEqual((magic,count,address,entry),(b'EBA1',32,0x4000,0x4010))
        row,_=volume.entry('BOOT.LDR');maps,pointers=volume.chain(int.from_bytes(row[1:3],'little'))
        self.assertEqual(pointers[:count],list(range(first,first+count)))
        self.assertEqual(row[0]&1,1)
        self.assertEqual(volume.entry('EXEC816.XEX')[0][0]&1,1)
        body=b''.join(volume.image.sector(n) for n in pointers[:count])
        self.assertEqual(hashlib.sha256(body).hexdigest(),self.report['reader']['disk-boot-reader.s']['sha256'])
        self.assertEqual(body[:16],bytes([0xa5])*16)
        self.assertEqual(body[-16:],bytes([0xa5])*16)

    def test_rom_header_and_phase_budget(self):
        volume=Volume(self.image.read_bytes());boot=volume.image.sector(1)
        self.assertEqual(boot[:9],bytes.fromhex('0003003077e44c8030'))
        self.assertEqual(boot[32:38],bytes.fromhex('2100017e0001'))
        self.assertEqual(set(self.report['reserved_bank_zero_delta'].values()),{0})
        self.assertEqual([x['bytes'] for x in self.report['boot_only_claims']],[384,8192])

    def test_reject_live_reader_or_os_overwrite(self):
        for start in (0,0x100,0x300,0x4000,0x5fff,0x8000):
            with self.subTest(address=start):
                p=self.root/'bad.xex';p.write_bytes(struct.pack('<HHHB',65535,start,start,0))
                with self.assertRaises(ValueError):check_layout(p)

    def test_reject_truncated_transport(self):
        p=self.root/'short.xex';p.write_bytes(self.xex.read_bytes()[:-1])
        with self.assertRaises(ValueError):check_layout(p)

    def test_repeated_markers_and_empty_file(self):
        p=self.root/'repeated.xex'
        p.write_bytes(b'\xff\xff'+self.xex.read_bytes())
        self.assertEqual(check_layout(p),301)
        p.write_bytes(b'\xff\xff')
        with self.assertRaises(ValueError):check_layout(p)


if __name__=='__main__':unittest.main()
