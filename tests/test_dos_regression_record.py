import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from dos_regression_record import validate

class DosRegressionRecordTests(unittest.TestCase):
    def test_selected_native_and_retained_fault_evidence_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/dos-regressions.json').read_text());validate(r)
        for fault in ('missing','guard','reuse','loader','lists','transport','lifetime','source','oracle','tx','budget'):
            b=copy.deepcopy(r)
            if fault=='missing':b['cases'].pop()
            elif fault=='guard':b['cases'][0]['runtime']['guards']='corrupt'
            elif fault=='reuse':next(c for c in b['cases'] if c['name']=='tasks')['runtime']['created']=1
            elif fault=='loader':next(c for c in b['cases'] if c['name']=='loader3')['build']['kernel_bank']=1
            elif fault=='lists':next(c for c in b['cases'] if c['name']=='lists-shared')['program']['sites']=[0]
            elif fault in ('transport','lifetime'):b['dependencies'][fault]['status']='fail'
            elif fault=='source':b['inputs']['lib/siodriver.act']='stale'
            elif fault=='oracle':b['oracle_replay'].pop()
            elif fault=='tx':b['tx_negative_control']['verdict']='pass'
            else:b['bank_zero']['fixed_delta']=1
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(b)

if __name__=='__main__':unittest.main()
