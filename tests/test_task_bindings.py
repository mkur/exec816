"""Reject incompatible public Task layouts and native import shapes."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_tasks import ABI, check_routine, constants, generate_kernel, policy_modules, validate_memory, writable_bindings


class TaskBindingsTests(unittest.TestCase):
    def test_boot_configuration_is_not_a_task_entry(self):
        from generate_tasks import application_entry
        self.assertFalse(application_entry({'name':'M_BOOTCONFIG_INIT_1234'}))
        self.assertFalse(application_entry({'name':'M_CONSOLECAPTURE_RELEASE_1234'}))
        self.assertTrue(application_entry({'name':'M_APPLICATION_WORKER_1234'}))

    def test_borrowed_storage_excludes_kernel_globals_and_preserves_bank_width(self):
        image = {'segments':[
            {'address':0x8800,'bytes':[0]*100,'writable':True,'executable':False},
            {'address':0x10000,'bytes':[0x6b],'writable':False,'executable':True},
            {'address':0x4ffef,'bytes':[0]*17,'writable':True,'executable':False}],
            'zero_fill':[{'address':0x50000,'size':25,'writable':True}],
            'data':[{'name':'M_TASKPOLICY_ROOTTASK_A','address':0x8820,'size':42}]}
        count,address = writable_bindings(image)
        self.assertEqual(count,3)
        self.assertEqual(address,0x5001a)
        raw = bytes(image['segments'][-1]['bytes'])
        pairs = [(int.from_bytes(raw[i:i+3],'little'),int.from_bytes(raw[i+4:i+7],'little'))
                 for i in range(0,len(raw),8)]
        self.assertEqual(pairs,[(0x8800,32),(0x884a,26),(0x4ffef,42)])
        self.assertFalse(image['segments'][-1]['writable'])

    def test_private_bindings_and_public_calls(self):
        from generate_memory import layout
        validate_memory(layout())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            generate_kernel(output,entries=[0x1ffff],writable=(3,0x5001a),memory=layout())
            bindings = (output/'tasks-bindings.inc').read_text()
            self.assertIn('.faraddr $05001a',bindings)
            directory = policy_modules(output)
            source = (directory/'exec.act').read_text()
            for name in ABI['imports']:
                self.assertIn(' '+name+'(',source)
            for name in ('TaskId','ExitTask','Lock','Unlock'):
                self.assertNotIn(' '+name+'(',source)
            extension = (directory/'exectasks.act').read_text()
            self.assertIn('Sleep(CARD ticks)',extension)
            self.assertNotIn('Create(',extension)
            with self.assertRaisesRegex(RuntimeError,'Too many'):
                generate_kernel(output,entries=[0x10000]*17,memory=layout())

    def test_rejects_unaligned_address_fields_and_heap_selector_collision(self):
        bad = copy.deepcopy(ABI)
        bad['task']['fields'][5][2] = 15
        with self.assertRaisesRegex(RuntimeError, 'layout'):
            constants(bad)
        bad = copy.deepcopy(ABI)
        bad['services']['ADD_TASK'] = 15
        with self.assertRaisesRegex(RuntimeError, 'collision'):
            constants(bad)

    def test_rejects_truncated_pointer_and_missing_native_padding(self):
        for name in ('AddTask','SetTaskPri','CreateTask'):
            shape = copy.deepcopy(ABI['imports'][name])
            check_routine(shape,name)
            if name in ('AddTask','CreateTask'):
                shape['arguments'][0]['size'] = 2
            else:
                shape['outgoing_bytes'] = 4
            with self.assertRaisesRegex(RuntimeError, 'arguments'):
                check_routine(shape,name)

    def test_managed_storage_uses_upper_arena_only(self):
        from generate_memory import layout
        from generate_tasks import storage
        for capacity, size in ((4, 192), (8, 448)):
            memory = layout()
            memory['task_capacity'] = capacity
            c = storage(memory)
            self.assertEqual(c['MANAGED_BYTES'], size)
            self.assertEqual(c['MANAGED'] % 2, 0)
            self.assertGreaterEqual(c['MANAGED'], c['BASE'])
            self.assertLessEqual(c['METADATA_END'], c['BASE'] + 0x800)
            self.assertEqual(c['METADATA_BYTES'], 768 if capacity == 4 else 1280)

    def test_collision_with_other_service_families(self):
        for selector in (0, 32, 40, 52):
            bad = copy.deepcopy(ABI)
            bad['services']['CREATE_TASK'] = selector
            with self.assertRaisesRegex(RuntimeError, 'collision'):
                constants(bad)
