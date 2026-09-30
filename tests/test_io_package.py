"""Validate the I/O contract and isolation of slice-2 test callees."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_io import ABI, SIO, RESULTS, constants, generate, public_api, check_routine, production_binding, IMPLEMENTED


class IOPackageTests(unittest.TestCase):
    def test_sizes_prefixes_and_signed_constants(self):
        c=constants()
        self.assertEqual([c[n+'_BYTES'] for n in ('IOREQUEST','IOSTDREQ','IOSIOREQ')],[26,42,52])
        self.assertEqual(ABI['records']['IOStdReq']['fields'][:6],ABI['records']['IORequest']['fields'])
        self.assertEqual(SIO['records']['IOSIOReq']['fields'][:10],ABI['records']['IOStdReq']['fields'])
        self.assertEqual(c['IOERR_OPENFAIL'],-1)
        self.assertEqual(c['IOERR_ABORTED'],-2)
        self.assertEqual(c['SIOERR_BADPROFILE'],9)
        self.assertIn('PUBLIC CONST IOERR_OPENFAIL=-1',public_api())
        self.assertEqual((Path(__file__).resolve().parents[1]/'lib/exec/exec-io-types.inc').read_text(),public_api())

    def test_staleness_and_host_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(directory);generate(directory,True)
            for name in ('io.inc','io-action.inc'):
                p=Path(directory)/name
                p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'))
                generate(directory,True)
                p.write_text(p.read_text()+'; stale\n')
                with self.assertRaises(ValueError):generate(directory,True)
                generate(directory)

    def test_rejects_collisions_with_all_service_families(self):
        # Gateway, Task, signal, heap, port, diagnostic and our own family.
        for selector in (1,17,26,15,32,58,59,60,41):
            a=copy.deepcopy(ABI);a['services']['OPEN_DEVICE']=selector
            with self.subTest(selector=selector),self.assertRaises(ValueError):constants(a)
        for error in (0xff11,0xff18,0xff60,0xff80):
            a=copy.deepcopy(ABI);a['errors']['MISUSE']=error
            with self.subTest(error=error),self.assertRaises(ValueError):constants(a)

    def test_rejects_narrowing_padding_and_prefix_changes(self):
        mutations=[lambda a:a['records']['IORequest']['fields'][0].__setitem__(1,'BYTE POINTER'),
                   lambda a:a['records']['IOStdReq']['fields'][-1].__setitem__(2,37),
                   lambda a:a['records']['IORequest'].update(alignment=1),
                   lambda a:a['records']['IOStdReq'].update(size=41),
                   lambda a:a['io_errors'].update(IOERR_OPENFAIL=255),
                   lambda a:a['imports']['OpenDevice']['arguments'][2].update(offset=7),
                   lambda a:a['imports']['OpenDevice']['arguments'][3].update(size=2),
                   lambda a:a['imports']['CreateIORequest'].update(outgoing_bytes=8),
                   lambda a:a['imports']['CheckIO'].update(result_bytes=2),
                   lambda a:a['imports']['WaitIO'].update(result_bytes=1)]
        for mutate in mutations:
            a=copy.deepcopy(ABI);mutate(a)
            with self.assertRaises(ValueError):constants(a)
        for mutate in (lambda s:s['records']['IOSIOReq']['fields'][-1].__setitem__(2,47),
                       lambda s:s['constants'].update(SIOERR_FRAMING=5),
                       lambda s:s.update(profiles={'unqualified':0})):
            s=copy.deepcopy(SIO);mutate(s)
            with self.assertRaises(ValueError):constants(sio=s)

    def test_native_results_and_no_production_test_stubs(self):
        for name,shape in ABI['imports'].items():
            check_routine(shape,name)
            interface={**copy.deepcopy(shape),'name':'EXEC.'+name,'result':RESULTS[shape['result_bytes']]}
            if name in IMPLEMENTED:
                self.assertEqual(production_binding(interface),'io_'+IMPLEMENTED[name])
            else:
                with self.assertRaisesRegex(ValueError,'Unimplemented device I/O import'):
                    production_binding(interface)
            interface['result']='Some(NativeResult(A8ZeroExtended))'
            with self.assertRaisesRegex(ValueError,'result ABI'):check_routine(interface,name)

    def test_qualification_requires_both_modes_and_rejected_public_bindings(self):
        from test_io import validate_record
        report=dict(status='pass',cases=[dict(name=name,status='pass',runtime=dict(guards='intact'),
            errors=[-1,-2,9],returns=[0xab1234,0x70000,0]) for name in ('abi-raw','abi-opt')],
            production_rejections=[dict(name=name,status='rejected') for name in ABI['imports']])
        validate_record(report)
        for fault in ('partial','unsigned','narrow','stub'):
            bad=copy.deepcopy(report)
            if fault=='partial':bad['cases'].pop()
            elif fault=='unsigned':bad['cases'][0]['errors'][0]=255
            elif fault=='narrow':bad['cases'][0]['returns'][1]=0
            else:bad['production_rejections'][0]['status']='bound'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate_record(bad)

    def test_residents_are_explicit_and_reservations_stay_upper(self):
        from generate_io import reserve_metadata, registration_include
        from generate_memory import layout
        from generate_heap import reserve_metadata as heap
        from generate_ports import reserve_metadata as ports
        from ports_budget import account
        from generate_tasks import validate_memory
        for bank in (1,3):
            memory=layout(kernel_bank=bank);heap(memory);ports(memory);validate_memory(memory)
            before=account(memory);reserve_metadata(memory)
            self.assertEqual(account(memory),before)
            slot=memory['upper_reservations'][-1]
            self.assertEqual((slot['address']>>16,slot['size']),(bank,256))
            self.assertEqual(memory['profile']['code_origin'],slot['address']+256)
            with tempfile.TemporaryDirectory() as directory:
                registration_include(directory,memory)
                self.assertIn('IS_TEST_DEVICE=0',Path(directory,'io-storage-action.inc').read_text())
                registration_include(directory,memory,True)
                self.assertIn('IS_TEST_DEVICE=1',Path(directory,'io-storage-action.inc').read_text())

    def test_published_queue_evidence_covers_the_slice(self):
        import json
        record=json.loads((Path(__file__).resolve().parents[1]/'docs/qualification/io-queues.json').read_text())
        self.assertEqual(record['status'],'pass')
        self.assertEqual(set(record['available']),set(ABI['imports']))
        self.assertEqual(record['unimplemented'],[])
        required={'queues','lifetime','queued_handoff','gap','queues-publication-2','queues-publication-3',
                  *('wait-fault-'+str(i) for i in range(4))}
        self.assertEqual({s['suite'] for s in record['suites']},required)
        for suite in record['suites']:
            self.assertEqual(suite['status'],'pass')
            self.assertEqual({c['build']['optimize'] for c in suite['cases']},{False,True})
            self.assertEqual(len(suite['cases']),2)
            for case in suite['cases']:
                self.assertEqual(case['status'],'pass')
                self.assertEqual(case['runtime']['guards'],'intact')
        self.assertEqual(record['production_worker_control']['status'],'rejected')
        self.assertFalse(record['production_worker_control']['executable_published'])
        self.assertTrue(all(a['kernel_near_name_bytes']==0 for a in record['near_storage_audit']))
        self.assertEqual(record['upper_device_arena'],dict(reserved=64,resident_slots=8,
                         queue_with_padding=24,names=31,final_padding=1))
        self.assertEqual(record['reservation_delta'],dict(fixed_bank_zero=0,per_task_bank_zero=0,upper_reserved_bytes=0))

    def test_generated_exec_contains_current_api(self):
        from generate_tasks import ABI as tasks, policy_modules
        with tempfile.TemporaryDirectory() as directory:
            source=(policy_modules(Path(directory))/'exec.act').read_text()
            for name in ABI['imports']:self.assertIn(' '+name+'(',source)
            for name in ('IORequest','IOStdReq','IOSIOReq'):self.assertIn('PUBLIC TYPE '+name+'=',source)
        self.assertEqual(tasks['version'],0x800)


if __name__=='__main__':unittest.main()
