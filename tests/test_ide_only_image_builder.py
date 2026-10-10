import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_ide_media import build
from make_data_disk import make
from ideplus_media import filesystem_atr,put_sector
from filesystem_audit import Audit

class IDEOnlyMedia(unittest.TestCase):
    def test_layout_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'source').mkdir()
            (folder/'source/README.TXT').write_text('partition bytes\n')
            make(folder/'disk.atr',folder/'source',sector_bytes=256,sectors=2880)
            atr=(folder/'disk.atr').read_bytes();raw,record=build(atr,atr)
        self.assertEqual(len(raw),4*1024*1024)
        self.assertEqual(raw[:6],b'\x10APT\x01\x12')
        self.assertEqual(raw[48:256],bytes(208))
        extents=[]
        for index,mapping in enumerate(record['partitions']):
            entry=raw[(index+1)*16:(index+2)*16]
            actual=raw[(index+16)*16:(index+17)*16]
            self.assertEqual(struct.unpack_from('<H',entry,10)[0],index+1)
            self.assertEqual(entry[:10]+entry[12:],actual[:10]+actual[12:])
            self.assertEqual(actual[10:12],bytes(2))
            self.assertEqual(entry[12],0xc0 if index==0 else 0x40)
            leader=mapping['leader']*512
            self.assertEqual(raw[leader:leader+8],b'APT\0META')
            self.assertEqual(filesystem_atr(raw,mapping,atr),atr)
            audit=Audit(atr);audit.sdfs();self.assertEqual(audit.files['README.TXT'],b'partition bytes\n')
            extents.append((mapping['leader'],mapping['start']+mapping['physical']))
        self.assertLessEqual(extents[0][1],extents[1][0])
        changed=bytearray(raw);m=record['partitions'][1]
        put_sector(changed,m['start'],3,256,4,b'x'*256)
        self.assertEqual(changed[:m['start']*512],raw[:m['start']*512])
        self.assertEqual(changed[m['start']*512+5*256:m['start']*512+6*256],raw[m['start']*512+5*256:m['start']*512+6*256])

if __name__=='__main__':unittest.main()
