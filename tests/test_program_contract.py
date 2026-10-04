"""Host checks for generated loader policy and independent byte fixtures."""
import json
from pathlib import Path
import sys
import unittest
import copy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import generate_program


class ProgramContract(unittest.TestCase):
    def test_generated_policy(self):
        self.assertEqual((ROOT/'lib/dos/o65-constants.inc').read_text().replace('\r\n','\n'),
                         generate_program.constants())
        self.assertEqual((ROOT/'lib/dos/command.act').read_text(),generate_program.command_api())
        self.assertEqual((ROOT/'lib/dos/command-results.inc').read_text(),generate_program.command_results())
        self.assertEqual((ROOT/'lib/dos/command-errors.inc').read_text(),generate_program.command_errors())
        self.assertEqual((ROOT/'lib/dos/command-modes.inc').read_text(),generate_program.command_modes())
        self.assertEqual((ROOT/'lib/dos/command-args.inc').read_text(),generate_program.command_args())
        self.assertEqual((ROOT/'lib/dos/program-kernel.inc').read_text(),generate_program.kernel_constants())

    def test_policy_caps_bound_address_arithmetic(self):
        abi = json.loads((ROOT/'abi/program.json').read_text())
        self.assertEqual(abi['profile'], 'actionc.o65.compact.v3')
        self.assertEqual(abi['limits']['FILE'], 256*1024)
        self.assertLess(abi['limits']['TEXT']+65535, 1 << 24)
        self.assertEqual(len(set(abi['errors'].values())), len(abi['errors']))

    def test_read_args_shape_and_process_limit(self):
        spec=generate_program.ABI['providers']['ReadArgs']
        self.assertEqual(generate_program.physical(spec),
                         ([dict(offset=0,size=3,alignment=1),dict(offset=3,size=3,alignment=1),
                           dict(offset=6,size=2,alignment=2),dict(offset=8,size=3,alignment=1),
                           dict(offset=12,size=2,alignment=2)],15,4))
        process=json.loads((ROOT/'abi/process.json').read_text())
        self.assertEqual(generate_program.ABI['argument_limits']['TEXT'],process['argument_limit'])
        self.assertEqual(generate_program.ABI['argument_limits']['FIELDS'],8)

    def test_provider_reservation_excludes_console_tables(self):
        console = json.loads((ROOT/'abi/console.json').read_text())['storage']
        start = generate_program.ABI['provider_offset']
        end = start+generate_program.ABI['provider_capacity']
        self.assertGreaterEqual(start, console['keymap_offset']+128)
        self.assertLessEqual(end, 65536)

    def test_provider_manifest_rejects_unchecked_and_mismatched_builds(self):
        routines=[dict(name='M_PROGRAMPROVIDERS_RESOLVE_A')]
        address=0x38000
        for name,spec in generate_program.ABI['providers'].items():
            args,incoming,result=generate_program.physical(spec)
            routines.append(dict(name='M_PROGRAMAPI_'+name.upper()+'_B',signature=123,
                                 address=address,size=10,arguments=args,outgoing_bytes=incoming,result_bytes=result))
            address+=16
        image=dict(routines=routines,segments=[dict(address=0x38000,bytes=[0]*1024,executable=True)])
        labels=dict(stack_overflow=0x3200,stack_overflow_end=0x3210)
        payload,providers=generate_program.provider_manifest(image,labels,True)
        self.assertEqual(int.from_bytes(payload[4:8],'little'),len(payload))
        self.assertLessEqual(len(payload),generate_program.ABI['provider_capacity'])
        self.assertTrue(all(p['contract']['domains']==1 for p in providers[1:]))
        with self.assertRaisesRegex(ValueError,'checked kernel'):
            generate_program.provider_manifest(image,labels,False)
        bad=copy.deepcopy(image);bad['routines'][1]['arguments'][0]['size']=2
        with self.assertRaisesRegex(ValueError,'ABI mismatch'):
            generate_program.provider_manifest(bad,labels,True)
        bad=copy.deepcopy(image);bad['routines'][1]['address']=0x48000
        with self.assertRaisesRegex(ValueError,'executable storage'):
            generate_program.provider_manifest(bad,labels,True)

    def test_cstring_groups_bind_exact_signatures_and_native_shapes(self):
        libraries=generate_program.library_contracts(ROOT/'build/actionc')
        routines=[dict(name='M_PROGRAMPROVIDERS_RESOLVE_A')]
        address=0x38000
        for prefix,providers in [('PROGRAMAPI',generate_program.ABI['providers']),
                                 ('CSTRING_IMPL',libraries[0]['providers'])]:
            for name,spec in providers.items():
                args,incoming,result=generate_program.physical(spec)
                routines.append(dict(name='M_'+prefix+'_'+name.upper()+'_B',signature=spec.get('signature',123),
                                     address=address,size=10,arguments=args,outgoing_bytes=incoming,result_bytes=result))
                address+=16
        image=dict(routines=routines,segments=[dict(address=0x38000,bytes=[0]*1024,executable=True)])
        labels=dict(stack_overflow=0x3200,stack_overflow_end=0x3210)
        payload,providers=generate_program.provider_manifest(image,labels,True,libraries)
        self.assertEqual(len(payload),1111)
        self.assertEqual(len(providers),33)
        strlen=next(p for p in providers if p['name']=='cstring_strlen_v1')
        body=next(r for r in routines if r['name'].startswith('M_CSTRING_IMPL_STRLEN_'))
        self.assertEqual(strlen['address'],body['address'])
        self.assertEqual(strlen['contract']['arguments'],[dict(offset=0,size=3,alignment=1)])
        self.assertEqual(generate_program.physical(libraries[0]['providers']['strnlen'])[0],
                         [dict(offset=0,size=3,alignment=1),dict(offset=4,size=3,alignment=2)])
        self.assertEqual(generate_program.physical(libraries[0]['providers']['u32toa']),
                         ([dict(offset=0,size=4,alignment=2),dict(offset=4,size=3,alignment=1),
                           dict(offset=8,size=3,alignment=2)],11,3))
        bad=copy.deepcopy(image);bad['routines'][-1]['signature']^=1
        with self.assertRaisesRegex(ValueError,'signature mismatch'):
            generate_program.provider_manifest(bad,labels,True,libraries)
        bad=copy.deepcopy(image);bad['routines'][-1]['arguments'][1]['size']=2
        with self.assertRaisesRegex(ValueError,'ABI mismatch'):
            generate_program.provider_manifest(bad,labels,True,libraries)
        interface=dict(name='CSTRING.strlen',symbol=1,signature=body['signature'],abi=libraries[0]['abi'],
                       arguments=body['arguments'],outgoing_bytes=body['outgoing_bytes'])
        self.assertEqual(generate_program.command_import(interface,libraries)['name'],'cstring_strlen_v1')
        interface['signature']^=1
        with self.assertRaisesRegex(ValueError,'interface mismatch'):
            generate_program.command_import(interface,libraries)
        interface['name']='CSTRING.IMPL.strlen'
        with self.assertRaisesRegex(ValueError,'Unsupported command interface'):
            generate_program.command_import(interface,libraries)
