import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from dos_concurrency_record import validate

class DosConcurrencyRecordTests(unittest.TestCase):
    def test_complete_matrix_and_timing_fail_closed(self):
        r=json.loads((ROOT/'docs/qualification/dos-concurrency.json').read_text());validate(r)
        for fault in ('matrix','stock','guard','live','progress','bytes','source','pin','media','bus','stack','bank','packet','replay','rx','worker','alarm','time','vbi','dependency'):
            b=copy.deepcopy(r);c=next(c for c in b['matrix'] if c['capacity']==8 and c['timing'] is not None)
            if fault=='matrix':b['matrix'].pop()
            elif fault=='stock':b['stock'].pop()
            elif fault=='guard':c['runtime']['guards']='corrupt'
            elif fault=='live':c['observed']['peakTasks']=4
            elif fault=='progress':c['observed']['activeWork']=0
            elif fault=='bytes':c['observed']['totalBytes']-=1
            elif fault=='source':c['build']['task_inputs']['lib/fsworker.act']='stale'
            elif fault=='pin':c['build']['override']=True
            elif fault=='media':c['media'][0]='changed'
            elif fault=='bus':c['bus_released']=False
            elif fault=='stack':c['stacks'][1]['untouched_above_floor']=-1
            elif fault=='bank':c['bank_zero']['runtime_including_os']+=1
            elif fault=='packet':c['timing']['packets']['count']-=1
            elif fault=='replay':c['replay']['status']='missing'
            elif fault=='rx':c['timing']['rx_service']['max_us']=80
            elif fault=='worker':c['timing']['post_to_worker']['max_us']=100001
            elif fault=='alarm':c['timing']['alarms']['sio_watchdog']['max_us']=101
            elif fault=='time':c['timing']['elapsed_seconds']=c['limits']['guest_seconds']+1
            elif fault=='vbi':c['vbi_dispatches']=0
            else:b['dependencies']['transport']['status']='fail'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(b)

if __name__=='__main__':unittest.main()
