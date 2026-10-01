"""Task build contract checks independent of the emulator integration suite."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from generate_memory import layout
from generate_tasks import ABI, constants, generate_kernel, public_api, validate_memory
from native_program import kernel_source


class TaskPackageTests(unittest.TestCase):
    def test_reserved_pools_and_reclamation(self):
        memory = layout()
        validate_memory(memory)
        self.assertEqual(memory['reclaimed_after_adopt'], ['loader', 'staging'])
        self.assertEqual(len(memory['task_pools']), 5)
        for address in (0x0900, 0x0a00, 0x0c00, 0x13f0, 0x2400, 0x42b0, 0x5bf0, 0x6800):
            damaged = layout()
            damaged['regions']['foreign'] = [address, address+16]
            with self.assertRaisesRegex((RuntimeError,ValueError), 'overlap'):
                validate_memory(damaged)

    def test_native_packing_and_public_contract(self):
        c = constants()
        self.assertEqual([c['TCB_'+name] for name in ('SAVEDS', 'STATE', 'DP', 'STACKTOP', 'ENTRY')],
                         [6, 8, 16, 20, 22])
        self.assertEqual(ABI['constants']['SIZE'], 64)
        self.assertEqual(ABI['constants']['ENTRY_CAPACITY'], 16)
        self.assertEqual([c['TCB_WAITREASON'], c['TCB_WAKENODE']], [3, 32])
        self.assertIn('PUBLIC CONST TASK_SIZE=$3e', public_api())

    def test_stable_binding_storage_and_capacity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            labels = {'native_return':0x3100, 'idle_start':0x3a00, 'general_task_start':0x3a10}
            generate_kernel(path, labels, [0x010000, 0x123456], memory=layout())
            action = (path/'tasks-action.inc').read_bytes()
            self.assertIn('.faraddr $123456', (path/'tasks-bindings.inc').read_text())
            generate_kernel(path, labels, [0x020000], memory=layout())
            self.assertEqual(action, (path/'tasks-action.inc').read_bytes())
            with self.assertRaisesRegex(RuntimeError, 'Too many task entries'):
                generate_kernel(path, labels, [0x10000]*17, memory=layout())

    def test_root_source_line_endings(self):
        source = 'MODULE DEMO\nUSE EXEC\nUSE EXECTASKS\nPROC Main()\nRETURN\nENDMODULE\n'
        lf = kernel_source(source)
        crlf = kernel_source(source.replace('\n','\r\n'))
        self.assertEqual(lf, crlf)
        self.assertEqual(lf.count('USE EXECMEMORY'), 1)

    def test_entry_registration_checks_native_prototypes(self):
        from generate_tasks import task_entries
        def routine(name, address, arguments=None, result=0):
            return {'name':name, 'address':address, 'arguments':arguments or [],
                    'result_bytes':result, 'outgoing_bytes':1}
        image = {'entry':0x10001, 'segments':[{'address':0x10000, 'bytes':[0]*8, 'executable':True}],
                 'routines':[routine('M_APP_CHILD_A', 0x10002), routine('M_APP_MAIN_B', 0x10001),
                             routine('M_TASKPOLICY_INIT_C', 0x10003),
                             routine('M_APP_WITHARG_D', 0x10004, [1]),
                             routine('M_APP_FUNCTION_E', 0x10005, result=2)]}
        self.assertEqual(task_entries(image), [0x10001, 0x10002])
        for mutation in (lambda p: p['routines'][0].update(address=0x20000),
                         lambda p: p['routines'][0].update(outgoing_bytes=3),
                         lambda p: p['routines'][0].update(address=0x10001)):
            bad = copy.deepcopy(image)
            mutation(bad)
            with self.assertRaises(RuntimeError):
                task_entries(bad)

    def test_registered_driver_entries_exclude_helpers_and_require_a_body(self):
        from generate_tasks import task_entries
        from unittest.mock import patch
        def routine(name,address,args=()):
            return dict(name=name,address=address,arguments=list(args),result_bytes=0,outgoing_bytes=1)
        image=dict(entry=0x10000,segments=[dict(address=0x10000,bytes=[0]*8,executable=True)],
                   routines=[routine('M_APP_MAIN_A',0x10000),
                             routine('M_DRIVER_MOD_WORKER_B',0x10001),
                             routine('M_DRIVER_MOD_STOP_C',0x10002)])
        with patch.dict(ABI,registered_entries=['DRIVER_MOD.Worker']):
            self.assertEqual(task_entries(image),[0x10000,0x10001])
            missing=copy.deepcopy(image);missing['routines'].pop(1)
            with self.assertRaisesRegex(RuntimeError,'Missing registered'):
                task_entries(missing)
            bad=copy.deepcopy(image);bad['routines'][1]['arguments']=[1]
            with self.assertRaisesRegex(RuntimeError,'zero-argument'):
                task_entries(bad)

    def test_registered_resident_overrides_application_module_exclusion(self):
        from generate_tasks import task_entries
        from unittest.mock import patch
        image=dict(entry=0x10000,
                   segments=[dict(address=0x10000,bytes=[0]*8,executable=True)],
                   routines=[dict(name=name,address=0x10000+index,arguments=[],
                                  result_bytes=0,outgoing_bytes=1)
                             for index,name in enumerate(('M_APP_MAIN_A',
                                 'M_CONSOLEDRIVER_WORKER_B','M_CONSOLEDRIVER_START_C'))])
        with patch.dict(ABI,registered_entries=['CONSOLEDRIVER.Worker']):
            self.assertEqual(task_entries(image),[0x10000,0x10001])

    def test_policy_module_selection_is_isolated(self):
        from generate_tasks import policy_modules
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            selected = policy_modules(root)
            self.assertFalse((root/'exec.act').exists())
            self.assertIn('USE TASKPOLICY', (selected/'exec.act').read_text())
            self.assertIn(str(root/'tasks-action.inc'), (selected/'taskpolicy.act').read_text())

    def test_tasks_require_standard_memory_adoption(self):
        from native_program import build
        with self.assertRaisesRegex(RuntimeError, 'standard memory adoption'):
            build({}, Path('unused.act'), Path('unused-output'), tasks=True,
                  kernel_init_name='APP.UncheckedInit')

    def test_wake_probe_and_manual_drain_survive_source_line_endings(self):
        from generate_tasks import policy_modules
        from unittest.mock import patch
        read_text = Path.read_text

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outputs = []
            for crlf in (False, True):
                def source_text(path, *args, **kwargs):
                    text = read_text(path, *args, **kwargs)
                    if crlf and path.parent.name == 'exec':
                        return text.replace('\r\n', '\n').replace('\n', '\r\n')
                    return text

                with patch.object(Path, 'read_text', source_text):
                    selected = policy_modules(root, irq_probe=9, manual_wake=True)
                wakes = (selected/'task-wakes.inc').read_text()
                policy = (selected/'taskpolicy.act').read_text()
                self.assertEqual(wakes.count('  ClaimCheckpoint(ctx)'), 1)
                self.assertIn('  ClaimCheckpoint(ctx)\n  LET item=ctx.item', wakes)
                select = policy.split('CARD FUNC Select(', 1)[1].split(
                    'CARD FUNC Switch(', 1)[0]
                self.assertNotIn('DrainWakes()', select)
                self.assertIn('RETURN(selected)', policy.split(
                    'CARD FUNC FinishDispatch(', 1)[1].split(
                    'PUBLIC CARD FUNC Dispatch', 1)[0])
                outputs.append((wakes, policy))
            self.assertEqual(*outputs)
