"""Independent wire-trace and qualification-gate checks for the slice-1 probe."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from sio_transaction_trace import analyze, checksum, read_events
from sio_transactions import PIN, ROOT
from test_sio import CASES, budget, validate_record

LABELS={name:index+1 for index,name in enumerate((
    'stream_start','terminal_post','worker_wake','wait_call',
    'alarm_service','watchdog_service','critic_enter','critic_enter_next',
    'critic_leave','critic_leave_next'))}
DEFINITIONS=dict(SCENARIO=2,DIVISOR=0)


def cpu(tick,name):
    return ['cpu',str(tick),'0','8',f'{LABELS[name]:06x}',
            'abcd','1234','5678','47fe','2200','34','04','0']


def wire_trace():
    # One independent, valid unsupported-command/NAK exchange. Ticks are PAL
    # base cycles; every byte completes before COMMAND rises.
    rows=[cpu(1,'critic_enter'),cpu(10,'stream_start'),cpu(20,'wait_call'),
          ['command','100','1'],['timer','1800','0'],cpu(1820,'alarm_service'),
          ['idle','2600'],['command','4000','0'],['rxstart','4050','78','14'],
          ['receive','4180','78','32','223','255'],['read','4190','78'],
          cpu(4300,'terminal_post'),cpu(4330,'worker_wake'),cpu(4340,'critic_leave')]
    for i,byte in enumerate((49,0,0,0,49)):
        rows.append(['write',str(1890 if i==0 else 1920+(i-1)*140),str(byte),'0','0'])
        rows.append(['ready',str(1900+i*140),str(byte),'14','16'])
    for tick,masked in ((0,True),(500,False),(1800,True),(1850,False),
                        (4200,True),(4400,False),(5000,True)):
        rows.append(['mask',str(tick),'0','8','003000','04' if masked else '00',
                     '0','002fff','78' if masked else '58','0','0'])
    return sorted(rows,key=lambda row:int(row[1]))


def evaluate(rows):
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'wire.log'
        # Exercise universal newlines and exclusion of unrelated bridge text.
        path.write_bytes(('ignored private chatter\r\n'+''.join(
            '[SIOTXN] '+' '.join(row)+'\r\n' for row in rows)).encode())
        return analyze(path,LABELS,DEFINITIONS,PIN['limits'])


class SioTraceTests(unittest.TestCase):
    def test_complete_command_and_nak_pass(self):
        facts=evaluate(wire_trace())
        self.assertEqual(facts['verdict'],'pass',facts['violations'])
        self.assertEqual((facts['tx_bytes'],facts['rx_bytes']),(5,1))

    def test_functional_bytes_do_not_hide_deadline_or_phase_failure(self):
        for fault,violation in (('rx','late SERIN read'),('setup','command_setup outside profile window'),
                                ('hold','command_hold outside profile window'),
                                ('timer','late alarm service'),('reset','STIMER reset during transaction'),
                                ('missing','RX start/register/read count mismatch'),
                                ('tx','wrong transmitted frame bytes')):
            rows=wire_trace()
            if fault=='rx':next(r for r in rows if r[0]=='read')[1]='4320'
            elif fault=='setup':next(r for r in rows if r[0]=='command')[1]='1800'
            elif fault=='hold':[r for r in rows if r[0]=='command'][1][1]='3000'
            elif fault=='timer':next(r for r in rows if r[0]=='timer')[1]='1500'
            elif fault=='reset':rows.append(['register','4100','9','0'])
            elif fault=='missing':rows=[r for r in rows if r[0]!='read']
            else:next(r for r in rows if r[0]=='ready')[2]='48'
            with self.subTest(fault=fault):
                result=evaluate(sorted(rows,key=lambda r:int(r[1])))
                self.assertEqual(result['verdict'],'fail')
                self.assertIn(violation,result['violations'])

    def test_context_corruption_is_rejected(self):
        rows=wire_trace()
        next(r for r in rows if r[0]=='cpu' and int(r[4],16)==LABELS['worker_wake'])[5]='abce'
        with self.assertRaisesRegex(RuntimeError,'context changed'):evaluate(rows)

    def test_trace_clock_wrap_and_subcycles(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.log'
            path.write_bytes(b'[SIOTXN] command 4294967295 1\r\n'
                             b'[SIOPOC] cpu 0 3 8 003000 0000 0000 0000 47fe 2200 34 04 0\r\n')
            self.assertEqual([t for t,_ in read_events(path)],[4294967295,4294967296.375])

    def test_end_around_carry(self):
        self.assertEqual(checksum([255,1]),1)
        self.assertEqual(checksum([255,255,255,1]),1)
        self.assertEqual(checksum([49,82,4,0]),135)


class SioPackageTests(unittest.TestCase):
    def test_published_record(self):
        record=json.loads((ROOT/'docs/qualification/sio-feasibility.json').read_text())
        validate_record(record)
        self.assertEqual(record['platform'],PIN)
        self.assertEqual(record['memory'],budget())

    def test_historical_input_hashes(self):
        import hashlib,subprocess
        from historical_git import history_repository
        record=json.loads((ROOT/'docs/qualification/sio-feasibility.json').read_text())
        revision=record.get('source_revision')
        history=history_repository(ROOT,[revision]) if revision else ROOT
        for name,digest in record['inputs'].items():
            source=(subprocess.check_output(['git','show',revision+':'+name],cwd=history)
                    if revision else (ROOT/name).read_bytes())
            self.assertEqual(hashlib.sha256(source).hexdigest(),digest,name)

    def test_partial_or_false_success_cannot_qualify(self):
        record=json.loads((ROOT/'docs/qualification/sio-feasibility.json').read_text())
        for fault in ('partial','timing','replay','negative'):
            broken=copy.deepcopy(record)
            if fault=='partial':broken['cases'].pop()
            elif fault=='timing':broken['cases'][0]['timing']['verdict']='fail'
            elif fault=='replay':broken['cases'][0]['replay']['status']='skipped'
            else:next(c for c in broken['cases'] if c['negative_control'])['timing']['verdict']='pass'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate_record(broken)

    def test_complete_reservations_include_guards_slack_and_inspection(self):
        d=budget()['diagnostic']
        during=d['code']+d['state']+d['preflight_snapshot']+d['os_stack_with_guard']+d['contexts']*(
            d['per_context_dp_with_guards']+d['per_context_stack_with_guards'])
        self.assertEqual(d['bank_zero_during_probe'],during)
        self.assertEqual(d['bank_zero_with_inspection'],during+d['post_probe_inspection_code']+
                         d['post_probe_inspection_buffer'])
        self.assertEqual(budget()['production_delta'],dict(fixed_bank_zero=0,per_task_bank_zero=0))


if __name__=='__main__':unittest.main()
