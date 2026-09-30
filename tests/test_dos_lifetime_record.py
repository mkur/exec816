import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from dos_lifetime_record import validate,ARCHIVAL_BACKEND_MODULES
class DosLifetimeRecordTests(unittest.TestCase):
    def test_lifecycle_and_publication_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/dos-lifetime.json').read_text());validate(r)
        for fault in ('startup','capacity','lifetime','publication','offline','source','guard','reset','stack','eager','reuse','transport','arithmetic','budget'):
            b=copy.deepcopy(r)
            if fault in ('startup','capacity','lifetime','publication','offline'):b[fault].pop()
            elif fault=='source':b['startup'][0]['build']['task_inputs']['lib/fsboot.act']='stale'
            elif fault=='guard':b['lifetime'][0]['runtime']['guards']='corrupt'
            elif fault=='reset':b['offline'][0]['reset_required']=False
            elif fault=='stack':b['offline'][0]['stacks'][0]['untouched_above_floor']=-1
            elif fault=='eager':next(c for c in b['publication'] if c['name']=='empty')['runtime']['created']=1
            elif fault=='reuse':b['client_regressions'].pop()
            elif fault=='transport':b['transport']['status']='fail'
            elif fault=='arithmetic':b['arithmetic'][0]['cases']=1
            else:b['bank_zero']['fixed_delta']=1
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(b)
    def test_fresh_schema_requires_cancellation_signal_rollback(self):
        r=json.loads((ROOT/'docs/qualification/dos-lifetime.json').read_text());r['schema_version']=2
        with self.assertRaises(RuntimeError):validate(r)
        for mode in (False,True):
            case=copy.deepcopy(next(c for c in r['startup'] if c['fault']=='arrival' and c['build']['optimize']==mode))
            case['fault']='cancel-signal';r['startup'].append(case)
        validate(r)
        r['startup'].pop()
        with self.assertRaises(RuntimeError):validate(r)
    def test_backend_allocations_are_required_for_new_records(self):
        r=json.loads((ROOT/'docs/qualification/dos-lifetime.json').read_text());r['schema_version']=3
        for mode in (False,True):
            for fault in ('cancel-signal','backend-work','backend-volume'):
                case=copy.deepcopy(next(c for c in r['startup'] if c['fault']=='arrival' and c['build']['optimize']==mode))
                case['fault']=fault;r['startup'].append(case)
        for path in ARCHIVAL_BACKEND_MODULES:
            r['inputs'][path]='synthetic-backend-hash'
            for group in ('startup','capacity','lifetime','publication','offline'):
                for case in r[group]:case['build']['task_inputs'][path]='synthetic-backend-hash'
        validate(r)
        r['startup'].pop()
        with self.assertRaises(RuntimeError):validate(r)
if __name__=='__main__':unittest.main()
