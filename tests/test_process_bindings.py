"""Process placement and ABI boundaries, independent of native execution."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_process import check_calls, check_public, reserve_metadata, state_source, resident_entries, ABI
from generate_program import ABI as PROGRAM_ABI
from generate_tasks import task_entries, writable_bindings
from generate_memory import layout


class ProcessBindingsTests(unittest.TestCase):
    def test_generated_contract_and_upper_placement(self):
        check_public()
        memory = layout()
        before = copy.deepcopy(memory['regions'])
        reserve_metadata(memory,8)
        self.assertEqual(memory['regions'],before)
        storage = memory['process_storage']
        self.assertGreaterEqual(storage['BASE'],65536)
        self.assertEqual(storage['BYTES'],1028)
        self.assertIn(f'ADDRESS(${storage["BASE"]:x})',state_source(8,storage['BASE']))
        bad = layout()
        bad['profile']['code_origin'] = (bad['constants']['KERNEL_BANK']+1)*65536-512
        with self.assertRaisesRegex(ValueError,'exceeds kernel bank'):
            reserve_metadata(bad,8)

    def test_only_embedded_tasks_are_admitted_writable(self):
        image = dict(segments=[dict(address=0x14000,bytes=[0]*1028,writable=True)],zero_fill=[],
                     data=[dict(name='M_PROCESSSTATE_TABLE',address=0x14000,size=1028)])
        count,_ = writable_bindings(image)
        self.assertEqual(count,8)
        raw = bytes(image['segments'][-1]['bytes'])
        pairs = [(int.from_bytes(raw[i:i+3],'little'),int.from_bytes(raw[i+4:i+7],'little'))
                 for i in range(0,len(raw),8)]
        self.assertEqual(pairs,[(0x14000+128*i,62) for i in range(8)])

    def test_process_helpers_do_not_become_command_entries(self):
        names = ['M_APP_MAIN_A','M_PROCESS_RUN_B','M_PROCESS_FINISH_C','M_PROCESS_HELPER_D',
                 'M_APP_SHELLEXTERNAL_E','M_APP_SHELLCOMMAND_F','M_APP_SHELLDIR_A']
        image = dict(entry=0x10000,segments=[dict(address=0x10000,bytes=[0]*len(names),executable=True)],
                     routines=[dict(name=n,address=0x10000+i,arguments=[],result_bytes=0,outgoing_bytes=1)
                               for i,n in enumerate(names)])
        self.assertEqual(task_entries(image),[0x10000,0x10001,0x10002])

    def test_rejects_process_call_shape_changes(self):
        routine = dict(name='M_PROCESS_START_A',outgoing_bytes=9,result_bytes=4,
                       arguments=[dict(size=3,alignment=1,offset=0),dict(size=3,alignment=1,offset=3),
                                  dict(size=2,alignment=2,offset=6)])
        check_calls(dict(routines=[routine]))
        for key,value in [('outgoing_bytes',7),('result_bytes',2),('arguments',[])]:
            changed = dict(routine,**{key:value})
            with self.assertRaisesRegex(ValueError,'call shape changed'):
                check_calls(dict(routines=[changed]))

    def test_function_entries_are_separate_and_exactly_typed(self):
        def routine(name, address, signature=PROGRAM_ABI['entry_signature'], result=4):
            return dict(name=name,address=address,size=1,signature=signature,
                        arguments=[],result_bytes=result,outgoing_bytes=1)
        image=dict(entry=0x10000,segments=[dict(address=0x10000,bytes=[0]*256,executable=True)],
                   routines=[routine('M_APP_MAIN_A',0x10000,result=0),
                             routine('M_APP_CHILD_B',0x10001),
                             routine('M_PROCESS_EXECUTEIMAGE_C',0x10002),
                             routine('M_APP_UNSIGNED_D',0x10003,signature=123),
                             routine('M_PROGRAMAPI_IOERR_E',0x10004),
                             routine('M_PROCESS_HELPER_F',0x10005)])
        self.assertEqual(task_entries(image),[0x10000])
        self.assertEqual(resident_entries(image),[0x10001,0x10002])
        bad=copy.deepcopy(image);bad['routines'][1]['address']=0x20000
        with self.assertRaisesRegex(ValueError,'outside executable'):
            resident_entries(bad)
        image['routines']=[routine(f'M_APP_CHILD_{i:X}',0x10000+i)
                           for i in range(ABI['resident_entries']['capacity']+1)]
        with self.assertRaisesRegex(ValueError,'Too many'):
            resident_entries(image)
