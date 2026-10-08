"""Check the disk/boot split independently of the target reader."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gem_component import prepare


class GemComponentTests(unittest.TestCase):
    def test_fixed_header_payload_and_identity_cover_layout_and_bss(self):
        foreign = dict(segments=[dict(address=0xc0000,bytes=list(b'123456789'),
            executable=True,writable=False)],zero_fill=[dict(address=0xd0000,size=48,writable=True)],
            provenance={})
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            first=prepare(copy.deepcopy(foreign),output)
            raw=(output/'GEMSYS.BIN').read_bytes()
            magic,version,count,size,identity,crc,pad=struct.unpack('<4sHHI16sHH',raw[:32])
            self.assertEqual((magic,version,count,size,crc,pad),(b'G816',1,1,9,0x29b1,0))
            self.assertEqual(raw[32:],b'123456789')
            self.assertEqual(first['sha256'],hashlib.sha256(raw).hexdigest())
            emitted=json.loads((output/'c-image.json').read_text())
            self.assertTrue(emitted['segments'][0]['deferred'])
            self.assertEqual(emitted['segments'][0]['bytes'],list(b'123456789'))
            for kind in ('address','bss','payload'):
                changed=copy.deepcopy(foreign)
                if kind=='address':changed['segments'][0]['address']+=65536
                elif kind=='bss':changed['zero_fill'][0]['size']+=1
                else:changed['segments'][0]['bytes'][-1]^=1
                record=prepare(changed,output)
                self.assertNotEqual(record['identity'],identity.hex())


if __name__=='__main__':
    unittest.main()
