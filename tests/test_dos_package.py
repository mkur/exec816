"""Native DOS package guards: no narrowing, selector collisions or public stubs."""
import copy,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_dos import ABI,RESULTS,constants,generate,public_api,check_routine,production_binding

class DosPackageTests(unittest.TestCase):
    def test_generated_contract(self):
        from generate_dos import check_public
        constants()
        check_public()
        self.assertEqual((ROOT/'lib/dos/dos-types.inc').read_text(),public_api())
        with tempfile.TemporaryDirectory() as d:
            generate(d);generate(d,True)
            p=Path(d)/'dos.inc';p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'));generate(d,True)
            p.write_text(p.read_text()+'; stale\n')
            with self.assertRaises(ValueError):generate(d,True)

    def test_collision_and_narrowing_rejected(self):
        for selector in (1,17,26,32,40,54,53,58,59,60):
            a=copy.deepcopy(ABI);a['services']['CONTEXT']=selector
            with self.subTest(selector=selector),self.assertRaises(ValueError):constants(a)
        for mutate in (lambda a:a['imports']['Read']['arguments'][-1].update(size=2),
                       lambda a:a['imports']['Seek'].update(result_bytes=2),
                       lambda a:a['records']['DosPacket']['fields'][-1].__setitem__(2,40),
                       lambda a:a['records']['FileInfoBlock'].update(alignment=4)):
            a=copy.deepcopy(ABI);mutate(a)
            with self.assertRaises(ValueError):constants(a)

    def test_no_successful_stubs(self):
        for name,shape in ABI['imports'].items():
            interface={**copy.deepcopy(shape),'name':'DOS.'+name,'result':RESULTS[shape['result_bytes']]}
            check_routine(interface,name)
            with self.assertRaisesRegex(ValueError,'Unimplemented DOS import'):production_binding(interface)
            interface['result']='Some(NativeResult(A16))'
            with self.assertRaisesRegex(ValueError,'DOS result ABI'):check_routine(interface,name)

    def test_context_storage_conserves_bank_zero(self):
        from generate_memory import layout
        from generate_heap import reserve_metadata as heap
        from generate_ports import reserve_metadata as ports
        from generate_io import reserve_metadata as io
        from generate_dos import reserve_metadata
        from task_capacity import configure
        from ports_budget import account
        from generate_tasks import validate_memory
        for capacity in (4,8):
            for bank in (1,3):
                memory=layout(kernel_bank=bank,upper_table=capacity==8)
                if capacity==8:configure(memory,8,1024,512)
                heap(memory);ports(memory);io(memory);validate_memory(memory);before=account(memory)
                reserve_metadata(memory,capacity)
                self.assertEqual(account(memory),before)
                self.assertEqual(memory['dos_storage']['BASE']>>16,bank)
                self.assertEqual(memory['dos_storage']['BYTES'],16*capacity)
                streams=memory['dos_storage']['STREAMS']
                self.assertEqual(streams>>16,bank)
                self.assertEqual(memory['dos_storage']['STREAM_BYTES'],64)
                self.assertIn(dict(name='dos-streams',address=streams,size=64),memory['upper_reservations'])
                self.assertLessEqual(streams+64,memory['profile']['code_origin'])
                self.assertGreaterEqual(streams,memory['dos_storage']['SHARED']+memory['dos_storage']['SERVICE_BYTES'])

    def test_published_abi_requires_execution_and_rejection(self):
        import json
        from test_dos_abi import validate_record
        r=json.loads((ROOT/'docs/qualification/dos-abi.json').read_text())
        validate_record(r)
        for fault in ('mode','guard','width','pointer','stub'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['cases'].pop()
            elif fault=='guard':bad['cases'][0]['runtime']['guards']='corrupted'
            elif fault=='width':bad['cases'][0]['routines']['Read']['result_bytes']=2
            elif fault=='pointer':bad['cases'][0]['returns'][0]=0
            else:bad['production_rejections'][0]['status']='bound'
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate_record(bad)

    def test_client_evidence_fails_closed(self):
        import json
        from dos_client_record import validate
        r=json.loads((ROOT/'docs/qualification/dos-client.json').read_text())
        validate(r)
        for fault in ('mode','case','source','reuse','timing','replay','publication','stack'):
            bad=copy.deepcopy(r)
            if fault=='mode':bad['suites'].pop()
            elif fault=='case':bad['suites'][0]['cases'].pop()
            elif fault=='source':bad['inputs']['lib/dosclient.act']='stale'
            elif fault=='reuse':
                next(c for c in bad['suites'][0]['cases'] if c['case']=='reuse')['runtime']['created']=255
            elif fault=='timing':bad['serial_regressions'][0]['timing']['verdict']='fail'
            elif fault=='replay':bad['serial_regressions'][0]['replay']['status']='different'
            elif fault=='publication':bad['publication']['cases'][0]['status']='bound'
            else:bad['stack_probes'][0]['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):validate(bad)

if __name__=='__main__':unittest.main()
