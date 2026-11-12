"""Passive observations must survive preemption and reject false boundaries."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from update_admission_trace import decode, read_value
from text_performance_trace import analyze_locks, busy_intervals, busy_markers, extend_clock, timeline
from sio_transaction_trace import BASE_HZ, read_events
from bitmap_console_performance import hardware_markers
from measure_gui_baseline import exposed_title, save_cpu_trace


def event(tick, pc, a=0, sp=0x1000, dp=0xb00, p=0):
    return tick, ['cpu', str(tick), '0', '8', f'{pc:x}', f'{a:x}', '0', '0',
                  f'{sp:x}', f'{dp:x}', '0', f'{p:x}', '0']


class AdmissionTrace(unittest.TestCase):
    def test_capture_can_begin_inside_an_outer_interrupt(self):
        points=dict(selected=0x300,native_irq=0x500,native_nmi=0x600,interrupt_schedule=0x700)
        rows=timeline([event(0,0x600,sp=0x1009),event(1,0x700,sp=0x1000),
            event(2,0x700,sp=0x1100),event(3,0x300),event(4,0x111)],points)
        self.assertEqual(rows[-1][2:],(0xb00,False))

    def test_unmatched_interrupt_exit_after_selection_still_fails(self):
        points=dict(selected=0x300,native_irq=0x500,native_nmi=0x600,interrupt_schedule=0x700)
        with self.assertRaisesRegex(RuntimeError,'Unbalanced'):
            timeline([event(0,0x300),event(1,0x700)],points)

    def test_terminal_title_point_is_outside_both_covering_windows(self):
        self.assertEqual(exposed_title((112,40,640,232),
            [(32,32,512,224),(480,32,624,80)]),(624,45))
        self.assertEqual(exposed_title((480,32,624,80),[(32,32,512,224)]),(512,37))
        self.assertEqual(exposed_title((32,32,512,224),[(480,32,624,80)]),(52,37))

    def test_completely_covered_title_fails_before_offering_a_click(self):
        with self.assertRaisesRegex(RuntimeError,'No exposed title'):
            exposed_title((112,40,640,232),[(0,0,640,240)])

    def test_debugger_clock_is_extended_to_the_capture_epoch(self):
        self.assertEqual(extend_clock(267581956,4562335844.25),4562549252)
        self.assertEqual(extend_clock(3,4294967290),4294967299)
        self.assertEqual(extend_clock(4562549252,4562335844.25),4562549252)

    def test_cpu_capture_preserves_clock_wrap_and_excludes_bridge_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            events=[event(4294967294,0x100),event(3,0x104)]
            (out/'emulator.log').write_text('[Bridge] private session metadata\n'
                '[SIOTXN] anchor 4294967290\n'+''.join(
                    '[SIOTXN] '+' '.join(e)+'\n' for _,e in events))
            save_cpu_trace(out)
            self.assertNotIn('private', (out/'cpu-trace.log').read_text())
            self.assertEqual([t for t,_ in read_events(out/'cpu-trace.log') if _[0]=='cpu'],
                [4294967294,4294967299])

    def test_outlined_launch_marker_is_checked_against_linked_code(self):
        raw=bytearray(64);raw[32:36]=bytes.fromhex('22300001')
        raw[48:57]=bytes.fromhex('e220a9018700c2206b')
        image=dict(symbols=dict(idle=0x10000,start=0x10020),
            segments=[dict(address=0x10000,bytes=list(raw))])
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'2-vbxe.lst').write_text('.section farcode,text\n'
                '\\ 000000 5a idle: phy\n\\ 000001 6b rtl\n'
                '.section farcode,text\n\\ 000000 start:\nREG(BUSY)=1;\n'
                '\\ 000000 22...... jsl long:store_helper\n\\ 000004 5c...... jmp long:epilogue\n')
            self.assertEqual(hardware_markers(dict(labels={}),image,folder)['launch']['entry'],0x10020)
            raw[32]=0xea;image['segments'][0]['bytes']=list(raw)
            with self.assertRaisesRegex(RuntimeError,'disagrees'):
                hardware_markers(dict(labels={}),image,folder)
            raw[32]=0x22;raw[51]=0;image['segments'][0]['bytes']=list(raw)
            with self.assertRaisesRegex(RuntimeError,'constant-one'):
                hardware_markers(dict(labels={}),image,folder)

    def test_busy_bounds_include_preemption_but_do_not_charge_it_as_hardware(self):
        points=dict(dma_launch=0x100,busy_read_start_0=0x200,busy_read_value_0=0x204)
        events=[event(0,0x100),event(2,0x200),event(3,0x204,a=1),
            event(4,0x300,dp=0xc00),event(10,0x200),event(11,0x204,a=3),
            event(12,0x200),event(13,0x204,a=0)]
        row=busy_intervals(events,points,0xb00)[0]
        self.assertEqual(row['busy_reads'],2)
        self.assertAlmostEqual(row['lower_ms'],7*1000/BASE_HZ)
        self.assertAlmostEqual(row['upper_ms'],13*1000/BASE_HZ)
        with self.assertRaisesRegex(RuntimeError,'Unfinished'):
            busy_intervals(events[:-2],points,0xb00)
        with self.assertRaisesRegex(RuntimeError,'Overlapping'):
            busy_intervals(events[:1]+[event(1,0x100,dp=0xc00)],points,0xb00)

    def test_immediately_idle_read_and_unrelated_owner(self):
        points=dict(dma_launch=0x100,busy_read_start_0=0x200,busy_read_value_0=0x204)
        events=[event(0,0x100,dp=0xc00),event(1,0x200,dp=0xc00),
            event(2,0x204,dp=0xc00),event(3,0x100),event(4,0x200),event(5,0x204)]
        rows=busy_intervals(events,points,0xb00)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['lower_ms'],0)
        self.assertEqual(rows[0]['start'],3)
        self.assertEqual(rows[0]['polls'],1)

    def test_busy_markers_require_linked_read_instructions(self):
        raw=bytearray(32)
        for offset in (4,20):raw[offset-4]=0x22;raw[offset:offset+3]=bytes.fromhex('890300')
        image=dict(symbols=dict(idle=0x10000),segments=[dict(address=0x10000,bytes=list(raw))])
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'2-vbxe.lst').write_bytes(b'.section farcode,text\r\n'
                b'\\ 000000 5a idle: phy\r\n\\ 000004 890300 bit ##3\r\n'
                b'\\ 000014 890300 bit ##3\r\n')
            self.assertEqual(busy_markers(folder,image)['busy_read_value_1'],0x10014)
            raw[4]=0xea;image['segments'][0]['bytes']=list(raw)
            with self.assertRaisesRegex(RuntimeError,'disagree'):
                busy_markers(folder,image)

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
