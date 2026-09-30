"""Current-directory evidence must retain its native, ownership and stack gates."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_directory_record import validate

class DirectoryRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        record=json.loads((ROOT/'docs/qualification/dos-current-directory.json').read_text())
        validate(record)
        for fault in ('case','status','bank','pointer','stack','layout','read'):
            bad=copy.deepcopy(record)
            if fault=='case':bad['cases'].pop()
            elif fault=='status':bad['cases'][0]['runtime']['status']=99
            elif fault=='bank':next(c for c in bad['cases'] if c['name']=='directory-bank3')['kernel_bank']=1
            elif fault=='pointer':next(c for c in bad['cases'] if c['name']=='abi')['returns'][17]=0
            elif fault=='stack':next(c for c in bad['cases'] if c['name']=='large-read')['runtime']['stack_observations'][0]['untouched_above_floor']=-1
            elif fault=='layout':bad['memory_delta']['client_allocation']=80
            else:next(c for c in bad['cases'] if c['name']=='large-read')['observations']['verified']=65535
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):
                validate(bad)

if __name__=='__main__':unittest.main()
