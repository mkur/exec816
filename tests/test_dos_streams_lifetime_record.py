import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_streams_lifetime_record import validate


class StreamLifetimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record=json.loads((ROOT/'docs/qualification/dos-streams-lifetime.json').read_text())

    def case(self,name):
        return next(c for c in self.record['cases'] if c['mode']=='raw' and c['name']==name)

    def test_passing_record(self):
        validate(self.record)

    def test_missing_case(self):
        self.record['cases'].pop()
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_unexercised_race(self):
        self.case('lifetime-bank1')['checkpoints'].pop()
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_unsafe_is_not_normal_cleanup(self):
        case=next(c for c in self.case('serial-256')['faults'] if c['name']=='short')
        case['runtime']['streams_cleanup']['unsafe_retained']=False
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_missing_causal_error(self):
        self.case('serial-128')['faults'].pop()
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_stack_reserve(self):
        self.case('lifetime-bank1')['runtime']['stack_observations'][2]['untouched_above_floor']=-1
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_extra_worker(self):
        self.case('console-only')['runtime']['created']+=1
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_changed_reservation(self):
        self.case('lifetime-bank3')['bank_zero']['runtime_including_os']+=16
        with self.assertRaises(RuntimeError):validate(self.record)


if __name__=='__main__':unittest.main()
