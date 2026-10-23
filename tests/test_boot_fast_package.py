"""Independent reconstruction of the ordinary-XEX takeover prefix."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_boot_fast import ABI,wrap,segment
from build_of816 import xex_segments


class BootFastPackage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.canonical=self.root/'core.xex'
        self.canonical.write_bytes(b'\xff\xff'+segment(0x6200,b'\x4c\x00\x62')+
                                   segment(0x2e0,struct.pack('<H',0x6200)))
        self.target=self.root/'boot.xex'
        self.record=wrap(self.canonical,self.target,self.root/'reader',None,'auto',native_divisor=40)

    def descriptor(self):
        raw=self.target.read_bytes();offset=self.record['descriptor_offset']
        return raw[offset:offset+ABI['descriptor']['size']]

    def test_payload_is_exact_and_independently_locatable(self):
        d=self.descriptor();offset=int.from_bytes(d[8:11],'little');size=int.from_bytes(d[11:14],'little')
        raw=self.target.read_bytes()
        self.assertEqual(raw[offset:],self.canonical.read_bytes())
        self.assertEqual(size,len(raw)-offset)
        self.assertEqual(d[14:30],hashlib.sha256(raw[offset:]).digest()[:16])
        self.assertEqual(int.from_bytes(d[30:33],'little'),self.record['descriptor_offset'])
        self.assertEqual(d[:8],b'BSI1\x01\x01\x01\x28')

    def test_external_loader_can_parse_complete_stream(self):
        segments=list(xex_segments(self.target.read_bytes()))
        self.assertEqual(segments[0],(0x6f00,b'\x4c\x00\x6f'))
        self.assertEqual(segments[1],(0x2e0,struct.pack('<H',0x6f00)))
        self.assertEqual(segments[-2:],list(xex_segments(self.canonical.read_bytes())))
        address,reader=segments[2]
        self.assertEqual(address,0x4000)
        self.assertEqual(len(reader),8192)
        self.assertEqual(reader[:16],b'\xa5'*16)
        self.assertEqual(reader[-16:],b'\xa5'*16)
        self.assertLessEqual(self.record['used_bytes'],self.record['reserved_bytes'])

    def test_rejects_payload_overwriting_live_reader(self):
        self.canonical.write_bytes(b'\xff\xff'+segment(0x4000,b'x'))
        with self.assertRaises(ValueError):wrap(self.canonical,self.target,self.root/'bad',None)

    def test_standard_policy_changes_only_prefix(self):
        other=self.root/'standard.xex'
        r=wrap(self.canonical,other,self.root/'standard',None,'standard',native_divisor=40)
        self.assertEqual(r['canonical_sha256'],self.record['canonical_sha256'])
        self.assertEqual(other.read_bytes()[r['prefix_bytes']:],self.canonical.read_bytes())
        at=r['descriptor_offset'];self.assertEqual(other.read_bytes()[at+5],0)

    def test_rejects_unknown_policy(self):
        with self.assertRaises(ValueError):wrap(self.canonical,self.target,self.root/'bad',None,'turbo')

    def test_shared_layout_and_generated_descriptor_fields(self):
        atr=json.loads((ROOT/'abi/boot-atr.json').read_text())
        for k in ('reader_address','reader_bytes','guard_bytes'):self.assertEqual(ABI[k],atr[k])
        inc=(self.root/'reader/boot-sio-defs.inc').read_text()
        for k,v in ABI['descriptor']['fields'].items():self.assertIn(f'BS_DESC_{k.upper()} = {v}\n',inc)


if __name__=='__main__':unittest.main()
