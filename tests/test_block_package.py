"""Publication and reproducibility gates for the sector boundary."""
import copy,hashlib,json,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from block_io_record import validate

class BlockPackageTests(unittest.TestCase):
    def test_compiler_bundle_matches_recorded_pin(self):
        # The bundle reproduces this historical gate, not later compiler pins.
        pin=json.loads((ROOT/'docs/qualification/block-io.json').read_text())['compiler']
        bundle=ROOT/pin['local_bundle']['path']
        self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(),pin['local_bundle']['sha256'])
        heads=subprocess.check_output(['git','bundle','list-heads',str(bundle)],text=True)
        self.assertEqual(heads.strip(),pin['revision']+' HEAD')

    def test_sector_evidence_fails_closed(self):
        r=json.loads((ROOT/'docs/qualification/block-io.json').read_text());validate(r)
        for fault in ('mode','provider','wire','rollback','source','guard','compiler'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['sectors'].pop()
            elif fault=='provider':next(c for c in bad['sectors'] if c['backend']=='fixture')['override_sha256']='unknown'
            elif fault=='wire':next(c for c in bad['sectors'] if c['backend']=='sio')['wire_commands']=11
            elif fault=='rollback':bad['allocation'].pop()
            elif fault=='source':bad['inputs']['lib/blockio.act']='stale'
            elif fault=='guard':bad['allocation'][0]['runtime']['guards']='corrupted'
            else:bad['compiler']['replay'][0]['status']='different'
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(bad)

if __name__=='__main__':unittest.main()
