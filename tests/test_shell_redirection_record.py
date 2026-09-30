import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from shell_redirection_record import validate
class ShellRedirectionRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        r=json.loads((ROOT/'docs/qualification/shell-redirection.json').read_text());validate(r)
        for fault in ('case','output','large','key','ownership','error','reserve'):
            b=copy.deepcopy(r)
            def case(name):return next(c for c in b['cases']if c['name']==name)
            if fault=='case':b['cases'].pop()
            elif fault=='output':case('basic-128')['writes_sha256']='0'*64
            elif fault=='large':case('large-256')['commands'][0]['source_bytes']=777
            elif fault=='key':case('physical')['schedule']=[s for s in case('physical')['schedule']if s['key']!='LESS']
            elif fault=='ownership':case('basic-128')['counts']['checks']=0
            elif fault=='error':case('fault-read-128')['commands'][0]['error']=0
            else:case('basic-128')['runtime']['stack_observations'][0]['untouched_above_floor']=-1
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(b)
