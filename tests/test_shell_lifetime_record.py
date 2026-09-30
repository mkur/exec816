import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from shell_lifetime_record import validate
class ShellLifetimeRecordTests(unittest.TestCase):
 def test_evidence_and_negative_controls(self):
  r=json.loads((ROOT/'docs/qualification/shell-lifetime.json').read_text());validate(r)
  for fault in ('case','directory','restore','cause','race','unsafe','serial','reuse','reserve'):
   b=copy.deepcopy(r)
   def case(name):return next(c for c in b['cases']if c['name']==name)
   if fault=='case':b['cases'].pop()
   elif fault=='directory':case('basic-bank1')['events'][-1]['objects']=3
   elif fault=='restore':case('restore-failure')['events'][-1]['done']=0
   elif fault=='cause':case('close-failure')['events'][1]['error']=202
   elif fault=='race':case('stream-races-bank1')['checkpoints'].pop()
   elif fault=='unsafe':case('serial-128')['serial_cases'][2]['runtime']['shell_cleanup']['shell_pointer']=0
   elif fault=='serial':case('serial-256')['serial_cases'].pop()
   elif fault=='reuse':case('reuse')['runtime']['created']=259
   else:case('basic-bank1')['runtime']['stack_observations'][0]['untouched_above_floor']=-1
   with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(b)
