"""Reject incomplete command, output, capacity and stack evidence."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from shell_commands_record import validate
class ShellCommandsRecordTests(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        r=json.loads((ROOT/'docs/qualification/shell-commands.json').read_text());validate(r)
        for fault in ('case','output','large','raw','memory','error','reserve','task'):
            b=copy.deepcopy(r)
            def case(s):return next(c for c in b['cases']if c['scenario']==s)
            if fault=='case':b['cases'].pop()
            elif fault=='output':b['cases'][0]['writes_sha256']='0'*64
            elif fault=='large':case('large')['commands'][0]['source_bytes']=777
            elif fault=='raw':case('raw-text')['observations']=[]
            elif fault=='memory':case('basic')['memory']['memAfter'][0]-=8
            elif fault=='error':case('fault-read')['commands'][0]['error']=0
            elif fault=='reserve':b['cases'][0]['runtime']['stack_observations'][0]['untouched_above_floor']=-1
            else:b['cases'][0]['runtime']['created']=4
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(b)
    def test_host_pacing_preserves_guest_image_and_ticks(self):
        r=json.loads((ROOT/'docs/qualification/headless-pacing.json').read_text())
        self.assertEqual([c['runtime']['native_nmi_count']for c in r['cases']],[50,50])
        self.assertEqual({c['xex_sha256']for c in r['cases']},{r['build']['xex_sha256']})
        for c in r['cases']:
            self.assertEqual(c['runtime']['guards'],'intact');self.assertEqual(c['runtime']['status'],0)
