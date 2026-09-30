"""Relative-path qualification requires ancestry, ownership and complete reads."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_relative_record import validate
class RelativeRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        record=json.loads((ROOT/'docs/qualification/dos-relative-paths.json').read_text());validate(record)
        for fault in ('case','layout','bank','media','base','depth','read','guard','abi-call','abi-width'):
            bad=copy.deepcopy(record)
            def case(name):return next(c for c in bad['cases'] if c['name']==name)
            if fault=='case':bad['cases'].pop()
            elif fault=='layout':bad['layouts']['service_heap']=432
            elif fault=='bank':case('bank3-128')['kernel_bank']=1
            elif fault=='media':case('bank1-128')['media']*=0
            elif fault=='base':case('bank1-256')['observations']['checks']=[56]
            elif fault=='depth':case('depth')['observations']['checks']=[13]
            elif fault=='read':case('relative-large')['observations']['verified']=65535
            elif fault=='abi-call':case('abi')['routines'].pop('NameFromLock')
            elif fault=='abi-width':case('abi')['routines']['Read']['result_bytes']=2
            else:case('bank1-128')['runtime']['guards']='damaged'
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(bad)
if __name__=='__main__':unittest.main()
