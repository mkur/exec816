import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from mydos_files_record import validate
class FileRecordTests(unittest.TestCase):
    def test_complete_and_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/mydos-files.json').read_text());validate(r)
        for fault in ('mode','high','source','damage','large','guard'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['cases'].pop()
            elif fault=='high':bad['cases'][0]['high_reads'].pop()
            elif fault=='source':bad['inputs']['lib/mydosfile.act']='changed'
            elif fault=='damage':bad['cases'][0]['phase_reads'].pop('41')
            elif fault=='large':next(c for c in bad['cases'] if c['sector_bytes']==256)['cases']=[]
            else:bad['cases'][0]['runtime']['guards']='bad'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(bad)
if __name__=='__main__':unittest.main()
