import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_directories_record import validate
class DirectoryRecordTests(unittest.TestCase):
    def test_complete_and_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/dos-directories.json').read_text());validate(r)
        for fault in ('mode','damage','source','entries','size','stack','abi'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['cases'].pop()
            elif fault=='damage':bad['damage'].pop()
            elif fault=='source':bad['inputs']['lib/fsdirectory.act']='changed'
            elif fault=='entries':bad['cases'][0]['oracle'].pop()
            elif fault=='size':next(c for c in bad['cases'] if c['sector_bytes']==256)['expected_sizes']['LARGE.BIN']=65535
            elif fault=='stack':bad['cases'][0]['stacks'][1]['untouched_above_floor']=-1
            else:bad['cases'][0]['public_shapes'].pop('ExNext')
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(bad)
if __name__=='__main__':unittest.main()
