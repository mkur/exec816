"""Published concurrency evidence must include every required target and replay."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sio_concurrent_record import validate
from historical_git import history_repository


class ConcurrentRecordTests(unittest.TestCase):
    def setUp(self):
        self.record=json.loads((ROOT/'docs/qualification/sio-concurrency.json').read_text())

    def test_complete_record(self):
        validate(self.record)

    def test_historical_pinned_inputs(self):
        import hashlib,subprocess
        revision=self.record.get('source_revision')
        history=history_repository(ROOT,[revision]) if revision else ROOT
        for name,digest in self.record['inputs'].items():
            source=(subprocess.check_output(['git','show',revision+':'+name],cwd=history)
                    if revision else (ROOT/name).read_bytes())
            self.assertEqual(hashlib.sha256(source).hexdigest(),digest,name)

    def test_partial_deadline_replay_capacity_and_fault_failures(self):
        for fault in ('partial','deadline','replay','capacity','identity','background','fault','control'):
            r=copy.deepcopy(self.record);case=next(c for c in r['cases'] if c['timing'])
            if fault=='partial':r['cases'].remove(case)
            elif fault=='deadline':case['timing']['verdict']='fail'
            elif fault=='replay':case['replay']['status']='skipped'
            elif fault=='capacity':case['observed']['peakTasks']=4 if case['observed']['peakTasks']==8 else 8
            elif fault=='identity':case['collection_order'][0]=255
            elif fault=='background':case['observed']['activeWork']=0
            elif fault=='fault':r['cases']=[c for c in r['cases'] if c['fault']!='timeout']
            else:r['negative_controls'].pop()
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(r)


if __name__=='__main__':unittest.main()
