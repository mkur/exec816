"""Reject C relinks that a bank-byte relocation stream cannot reproduce."""
import copy,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from c_program import fixups,verify,pack
from generate_c_program import files


def image(bank):
    base=bank<<16
    return dict(segments=[dict(address=base,bytes=[0x22,0x34,0x12,bank,0x5c,0x56,0x34,0x12],
                              executable=True,writable=False),
                          dict(address=base+65536,bytes=[0,0,bank,0],executable=False,writable=True)],
                zero_fill=[dict(address=base+65540,size=4,writable=True)],
                symbols=dict(main=base,ExecYield=base+4,privateData=base+65536),
                provenance=dict(dp_workspace_bytes=20))


class CProgramPackageTests(unittest.TestCase):
    def test_reconstruction_moves_internal_pointers_and_preserves_import_placeholder(self):
        original=image(12);relocations=fixups(original,image(13))
        self.assertEqual(relocations,[3,65538])
        for bank in (1,11,14,62):verify(original,image(bank),bank,relocations)
        wire,record=pack(original,relocations)
        self.assertEqual(struct.unpack_from('<4sHHBBHIIIHHI',wire),
                         (b'C816',1,2,12,64,3,65544,0,2,1,20,len(wire)))
        self.assertEqual(struct.unpack_from('<HHI',wire,32+3*16),(0,0,5))
        self.assertEqual(record['segments'][-1]['size'],4)
        self.assertEqual(wire[-12:],bytes(original['segments'][0]['bytes']+original['segments'][1]['bytes']))

    def test_rejects_changed_placement_and_unsupported_address_math(self):
        for change in ('layout','arithmetic'):
            altered=image(13)
            if change=='layout':altered['segments'][0]['address']+=1
            else:altered['segments'][0]['bytes'][3]+=1
            with self.assertRaises(RuntimeError):fixups(image(12),altered)

    def test_verification_rejects_later_bank_divergence_and_changed_symbols(self):
        for change in ('literal','symbol'):
            altered=image(62)
            if change=='literal':altered['segments'][0]['bytes'][1]^=1
            else:altered['symbols']['privateData']+=1
            with self.assertRaises(RuntimeError):verify(image(12),altered,62,[3,65538])

    def test_generated_native_limits_are_current(self):
        for path,content in files().items():self.assertEqual(path.read_text(),content)

if __name__=='__main__':unittest.main()
