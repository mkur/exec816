"""Passive observations must survive preemption and reject false boundaries."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from update_admission_trace import decode, read_value
from text_performance_trace import analyze_locks, timeline


def event(tick, pc, a=0, sp=0x1000, dp=0xb00, p=0):
    return tick, ['cpu', str(tick), '0', '8', f'{pc:x}', f'{a:x}', '0', '0',
                  f'{sp:x}', f'{dp:x}', '0', f'{p:x}', '0']


class AdmissionTrace(unittest.TestCase):
    def test_compact_timeline_keeps_off_cpu_readiness_boundary(self):
        points=dict(selected=0x300,ready=0x400,native_irq=0x500,
                    native_nmi=0x600,interrupt_schedule=0x700)
        segments=timeline([event(0,0x300),event(1,0x111),event(2,0x400),
                           event(3,0x112),event(4,0x113)],points)
        self.assertEqual(segments,[(0,2,0xb00,False),(2,4,0xb00,False)])

    def definition(self):
        return dict(routines={'policy':dict(entry=0x100,returns=[0x110],frame=4,
                    arguments=[dict(body_displacement=8,size=3)],instructions={
                        0x102:dict(raw='A3 08',asm='LDA $08,S'),
                        0x104:dict(raw='85 80',asm='STA $80'),
                        0x106:dict(raw='A3 09',asm='LDA $09,S'),
                        0x108:dict(raw='85 81',asm='STA $81'),
                        0x10a:dict(raw='A7 80',asm='LDA [$80]'),
                        0x10c:dict(raw='EA',asm='NOP')})},calls={},captures={})

    def test_arguments_and_reads_survive_interrupt(self):
        events=[event(1,0x100),event(2,0x102,sp=0xffc),
                event(3,0x104,a=0x1234,sp=0xffc),event(4,0x106,sp=0xffc),
                event(5,0x108,a=0x5612,sp=0xffc),event(6,0x10a,sp=0xffc),
                event(7,0x200,a=99),event(7.5,0x201,dp=0xa00,a=88),
                event(8,0x10c,a=0x789a,sp=0xffc),
                event(9,0x110,a=1)]
        rows,_=decode(events,self.definition())
        self.assertEqual(rows[0]['arguments'],[0x561234])
        self.assertEqual(read_value(rows[0],0x561234,2),0x789a)
        self.assertIsNone(read_value(rows[0],0x561234,4))

    def test_wrong_stack_return_fails(self):
        with self.assertRaisesRegex(RuntimeError,'Unbalanced'):
            decode([event(1,0x100),event(2,0x110,sp=0xfff)],self.definition())

    def test_missing_submission_fails(self):
        d=self.definition();d['captures']={0x200:'request_low'}
        with self.assertRaisesRegex(RuntimeError,'without caller'):
            decode([event(1,0x200)],d)

    def test_c_return_uses_stack_and_task(self):
        d=self.definition();d['calls']={0x200:dict(callee='ExecAESSubmit',end=0x204)}
        d['captures']={0x300:'request_low'}
        _,rows=decode([event(1,0x200,a=107),event(2,0x300,a=0x4567),
                       event(3,0x204,dp=0xc00),event(4,0x204,sp=0xff0),
                       event(5,0x204,a=1)],d)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['end'],5)
        self.assertEqual(rows[0]['request_low'],0x4567)
        self.assertEqual(rows[0]['value_in'],107)

    def test_sparse_calls_use_relocated_app_and_pair_begins_ends(self):
        definition=dict(reference=0x10000,local={0x10100:dict(end=0x10104)})
        record=dict(app=dict(base=0x20000),samples=[dict(operation='page',index=0,start=0,complete=8),
                                                dict(operation='line',index=0,start=9,complete=18)])
        events=[]
        for tick in (1,10):
            events.extend([event(tick,0x20100,a=1),event(tick+1,0x20104),
                           event(tick+2,0x20100,a=0),event(tick+3,0x20104)])
        # The same offsets in an unrelated bank cannot become viewer calls.
        events.insert(0,event(0,0x30100,a=1))
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            (out/'emulator.log').write_text(''.join('[SIOTXN] '+' '.join(e)+'\n' for _,e in events))
            result=analyze_locks(out,definition,record)
            self.assertEqual(result['page']['begin']['count'],1)
            self.assertEqual(result['line']['end']['count'],1)
            self.assertEqual(result['viewer_dp'],0xb00)
            events.pop()
            (out/'emulator.log').write_text(''.join('[SIOTXN] '+' '.join(e)+'\n' for _,e in events))
            with self.assertRaisesRegex(RuntimeError,'Incomplete'):
                analyze_locks(out,definition,record)
