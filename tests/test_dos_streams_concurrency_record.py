import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from dos_streams_concurrency_record import validate


class StreamConcurrencyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record=json.loads((ROOT/'docs/qualification/dos-streams-concurrency.json').read_text())

    def case(self,name='target256-raw'):
        return next(c for c in self.record['cases'] if c['name']==name)

    def test_complete_record(self):validate(self.record)

    def test_missing_matrix_case(self):
        self.record['cases'].pop()
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_short_read_not_full_read(self):
        self.case()['case']['counters']['verified']=777
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_deadline_miss(self):
        self.case()['timing']['deadline_misses']['rx']=1
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_relaxed_baud(self):
        self.case()['timing']['rx_byte_deadline_us']=80
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_missing_endpoint_intervals(self):
        self.case()['stream_timing']['endpoint_forbid']['count']-=1
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_replay_input_changed(self):
        self.case()['replay']['schedule'][0]['frame']+=1
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_lost_task(self):
        self.case()['case']['observations'][1]['live']=7
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_missing_tx_replay(self):
        self.record['tx'][0]['cases'].pop()
        with self.assertRaises(RuntimeError):validate(self.record)

    def test_stack_reserve_touched(self):
        self.case()['case']['runtime']['stack_observations'][2]['untouched_above_floor']=-1
        with self.assertRaises(RuntimeError):validate(self.record)


if __name__=='__main__':unittest.main()
