import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from trace_viewer_waits import atomic_events,ready_episodes,roster
from terminal_model import FIELDS


def event(pc,a=0,x=0,sp=0x4500,dp=0x800):
    return (0,['cpu','0','0','0',f'{pc:x}',f'{a:x}',f'{x:x}','0',f'{sp:x}',f'{dp:x}'])


def definition(kind,fields):
    return dict(spans={kind:dict(entry=0x100,returns=[0x101])},
        points={kind+'_'+field:0x200+i for i,field in enumerate(fields)})


class AtomicWaitTraceTests(unittest.TestCase):
    def test_signal_bits_reconstructed_before_masking(self):
        d=definition('signal',['target_low','target_high','old_low','old_high','xor_low','xor_high'])
        values=[0x123,0xab3f,0x4,0x20,0x4^0x5678,0x20^0x1234]
        events=[event(0x10,dp=0xd00),event(0x100)]
        events.extend(event(0x200+i,a=value,sp=0x44f0) for i,value in enumerate(values))
        events.append(event(0x101,a=4,x=0x20))
        row=atomic_events(events,d,0x10)[0]
        self.assertEqual(row['target'],0x3f0123)
        self.assertEqual(row['bits'],0x12345678)
        self.assertEqual(row['result'],0x200004)
        self.assertEqual(row['source_dp'],0xd00)

    def test_blocked_wait_keeps_both_mask_words(self):
        d=definition('wait',['target_low','target_high','mask_low','mask_high'])
        events=[event(0x100),event(0x200,a=0xda00),event(0x201,a=2),
            event(0x202,a=8),event(0x203,a=0x400),event(0x101)]
        row=atomic_events(events,d,0x10)[0]
        self.assertEqual(row['target'],0x2da00)
        self.assertEqual(row['mask'],0x4000008)

    def test_signal_clear_records_pending_reply_consumption(self):
        d=definition('signal',['target_low','target_high','old_low','old_high',
            'xor_low','xor_high','new_low','new_high'])
        values=[0x1422,2,0,0x20,0,0x20,0,0]
        events=[event(0x100)]+[event(0x200+i,a=v) for i,v in enumerate(values)]+[event(0x101,x=0x20)]
        row=atomic_events(events,d,0x10)[0]
        self.assertEqual(row['bits'],0)
        self.assertEqual(row['result'],0x200000)
        self.assertEqual(row['new_received'],0)

    def test_immediate_wait_does_not_invent_a_requested_mask(self):
        d=definition('wait',['target_low','target_high','mask_low','mask_high'])
        row=atomic_events([event(0x100),event(0x200,a=0xda00),event(0x201,a=2),
            event(0x101,x=2)],d,0x10)[0]
        self.assertEqual(row['result'],0x20000)
        self.assertNotIn('mask',row)

    def test_completion_uses_recipient_instead_of_previous_cpu_owner(self):
        d=definition('complete',['target_low','target_high'])
        row=atomic_events([event(0x10,dp=0xd00),event(0x100),event(0x200,a=0xda00),
            event(0x201,a=2),event(0x101,x=0x8000)],d,0x10)[0]
        self.assertEqual(row['source_dp'],0xd00)
        self.assertEqual(row['target'],0x2da00)
        self.assertEqual(row['result'],0x80000000)

    def test_bad_stack_and_incomplete_activation_fail(self):
        d=definition('complete',['target_low','target_high'])
        prefix=[event(0x100),event(0x200),event(0x201)]
        for events in (prefix,prefix+[event(0x101,sp=0x4400)]):
            with self.subTest(events=events),self.assertRaises(RuntimeError):
                atomic_events(events,d,0x10)

    def test_republished_ready_is_one_interval(self):
        changes=[(0,'blocked'),(10,'ready'),(12,'ready'),(20,'selected'),
            (30,'ready'),(50,'selected')]
        self.assertEqual(list(ready_episodes(changes,[20,50],60)),
            [(10,20,'after wait'),(30,50,'preemption/reschedule')])

    def test_initial_ready_episode_is_explicit_and_bounded(self):
        self.assertEqual(list(ready_episodes([(10,'ready')],[],50)),
            [(10,50,'initial/unknown')])

    def test_terminal_roster_keeps_process_identity_and_independent_masks(self):
        root=Path(__file__).resolve().parents[1]
        abi=json.loads((root/'abi/process.json').read_text())
        fields={f[0]:f[2] for f in abi['record']}
        table=0x21000;task=table+fields['task'];app=0x310100;port=0x330000
        raw=bytearray(abi['record_bytes']+4)
        raw[fields['state']]=1
        raw[fields['identity']:fields['identity']+4]=(4).to_bytes(4,'little')
        storage=dict(BASE=0x20000,SIZE=256,TCB_ITEM=0,TCB_ENTRY=4,
            TASK_TC_STATE=0,TASK_TC_SIGRECVD=4,TASK_TC_SIGWAIT=8,TASK_TC_TDNESTCNT=12)
        p=dict(build=dict(task_storage=storage,memory=dict(task_pools=[{'dp':0xd00},{'dp':0x1200},{'dp':0x1400}])),
            image=dict(data=[dict(name='M_PROCESSSTATE_TABLE',address=table,size=len(raw))],routines=[]))
        values={0x20100:task,task:1,0x310000:app,app+FIELDS['replies']:port,
            port+12:21,app+FIELDS['wake']:1<<22,app+FIELDS['paints']:26}
        session=SimpleNamespace(p=p,directory=root,report={'inputs':{}},
            b=SimpleNamespace(eval_expr=lambda expression:100),
            number=lambda address,size=4:values.get(address,0),at=lambda name:0,
            far=lambda address,size:bytes(raw) if address==table else b' '*size)
        instance=dict(task=task,name='terminal',identity=4,base=0x300000,symbols={'GEMTerminal':0x310000})
        with patch('trace_viewer_waits.instances',return_value=[instance]):
            row=roster(session,'initial')['tasks'][0]
        self.assertEqual((row['name'],row['process_identity']),('terminal',4))
        self.assertEqual(row['reply_mask'],1<<21)
        self.assertEqual(row['notification_mask'],1<<22)
        self.assertEqual(row['terminal_paints'],26)


if __name__=='__main__':unittest.main()
