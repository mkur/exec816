"""Core evidence rejects missing native, physical and ownership coverage."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from shell_core_record import validate
class ShellCoreRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        r=json.loads((ROOT/'docs/qualification/shell-core.json').read_text());validate(r)
        for fault in ('case','layout','key','stage','output','heap','entry','parser','reserve','task'):
            bad=copy.deepcopy(r)
            def case(name):return next(c for c in bad['cases']if c['name']==name)
            if fault=='case':bad['cases'].pop()
            elif fault=='layout':bad['shell_allocation']=1536
            elif fault=='key':case('physical')['schedule']=[e for e in case('physical')['schedule']if e['key']!='CTRL']
            elif fault=='stage':case('physical')['observations'].pop()
            elif fault=='output':case('physical')['exact_writes']=False
            elif fault=='heap':case('heap')['heap']['peakObjects']=2
            elif fault=='entry':case('entry')['commands'].pop()
            elif fault=='parser':case('parser')['checks']=91
            elif fault=='reserve':case('physical')['runtime']['stack_observations'][0]['untouched_above_floor']=-1
            else:case('physical')['runtime']['created']=4
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(bad)
if __name__=='__main__':unittest.main()
