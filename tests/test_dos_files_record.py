import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_files_record import validate
class DosFileRecordTests(unittest.TestCase):
    def test_complete_and_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/dos-files.json').read_text());validate(r)
        for fault in ('mode','fault','source','progress','stack','abi','guards'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['cases'].pop()
            elif fault=='fault':bad['faults'].pop()
            elif fault=='source':bad['inputs']['lib/fshandler.act']='changed'
            elif fault=='progress':bad['cases'][0]['io_progress']=[0]
            elif fault=='stack':bad['cases'][0]['stacks'][1]['untouched_above_floor']=-1
            elif fault=='abi':bad['cases'][0]['public_shapes'].pop('Seek')
            else:bad['cases'][0]['runtime']['guards']='bad'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(bad)
if __name__=='__main__':unittest.main()
