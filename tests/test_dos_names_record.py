"""Canonical-name qualification fails when ownership, ABI or bounds are absent."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_names_record import validate
class LockNamesRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        record=json.loads((ROOT/'docs/qualification/dos-lock-names.json').read_text());validate(record)
        for fault in ('case','layout','bank','allocation','bounds','abi','read','guard'):
            bad=copy.deepcopy(record)
            if fault=='case':bad['cases'].pop()
            elif fault=='layout':bad['layouts']['max_lock_allocation']=112
            elif fault=='bank':next(c for c in bad['cases'] if c['name']=='names-bank3')['kernel_bank']=1
            elif fault=='allocation':next(c for c in bad['cases'] if c['name']=='allocation')['override_sha256']=None
            elif fault=='bounds':next(c for c in bad['cases'] if c['name']=='bounds')['path_cases'].pop()
            elif fault=='abi':next(c for c in bad['cases'] if c['name']=='abi')['returns'][18]=65535
            elif fault=='read':next(c for c in bad['cases'] if c['name']=='large-read')['observations']['verified']=65535
            else:next(c for c in bad['cases'] if c['name']=='names-bank1')['runtime']['guards']='damaged'
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(bad)
if __name__=='__main__':unittest.main()
