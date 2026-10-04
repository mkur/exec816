import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import generate_console as console
import generate_memory as memory
import generate_tasks
import generate_input_native

class ConsoleLayoutTests(unittest.TestCase):
    def test_generated_files_and_public_request(self):
        self.assertEqual((console.ROOT/'lib/console/consoletypes.act').read_text(),console.types())
        self.assertEqual((console.ROOT/'platform/altirraos/console-layout.inc').read_text(),console.assembly())
        io=json.loads((console.ROOT/'abi/io.json').read_text())
        self.assertEqual(io['records']['IOStdReq']['size'],42)
        c=console.constants()
        native=generate_input_native.definitions()[0]
        self.assertEqual((native['RAWEVENT_SIZE'],native['RAWEVENT_ROUTE'],native['CAPTURE_SIZE']), (8,4,560))
        self.assertEqual((c['ROUTE_SIZE'],c['ROUTES_SIZE']), (16,264))
        self.assertEqual((c['INSTANCE_CELLORIGIN'],c['INSTANCE_SIZE']), (198,200))
        self.assertEqual(c['BATCH_SIZE'],44)
        self.assertLessEqual(console.ABI['storage']['instance_offset']+c['INSTANCE_SIZE'],
                             console.ABI['storage']['presentation_offset'])

    def test_console_build_admission(self):
        from native_program import build
        # Reject invalid publication before invoking any compiler or emitter.
        for options, message in (
            ({'console': 1}, 'boolean'),
            ({'console': True}, 'requires Tasks'),
            ({'console_test': True}, 'require Tasks'),
            ({'console': True, 'tasks': True, 'irq_probe': 10}, 'exclude the disposable probe'),
        ):
            with self.subTest(options=options), self.assertRaisesRegex(RuntimeError, message):
                build(None, None, None, **options)

    def test_bitmap_helpers_are_not_application_task_entries(self):
        for name in ('M_CONSOLEBITMAP_CLOSE_1234', 'M_CONSOLEBITMAP_POLL_1234',
                     'M_CONSOLEBATCH_RESET_1234'):
            self.assertFalse(generate_tasks.application_entry({'name': name}))

    def test_glyphs(self):
        table=console.glyphs()
        self.assertEqual(table[32:96],list(range(64)))
        self.assertEqual(table[97:123],list(range(97,123)))
        self.assertEqual([table[i] for i in (96,123,124,125,126,127)],[31,31,124,31,31,31])

    def test_layout_failures(self):
        for failure in ('offset','size','overlap','capture','tables','keymap','batch','collision'):
            a=copy.deepcopy(console.ABI)
            if failure=='offset':a['records']['Instance']['fields'][1][2]+=1
            if failure=='size':a['records']['Instance']['size']+=2
            if failure=='overlap':a['storage']['instance_offset']=0
            if failure=='capture':a['storage']['capture_offset']=0xff0
            if failure=='tables':a['storage']['glyph_offset']=0xff0
            if failure=='keymap':a['keymaps']['normal'][0]=256
            if failure=='batch':a['constants']['BATCH_MAX_ROWS']=5
            if failure=='collision':a['constants']['BATCH_ROWS']=4
            with self.subTest(failure=failure),self.assertRaises(ValueError):console.constants(a)

    def test_bank_selection_overlap_and_overflow(self):
        for bank in (1,3):
            m=memory.layout(memory.CONFIG,memory.PROFILE,kernel_bank=bank)
            console.reserve_metadata(m)
            self.assertEqual(m['console_storage']['BASE']>>16,bank)
            self.assertEqual(m['console_storage']['CAPTURE'],generate_tasks.storage(m)['BASE']+0xc00)
            self.assertEqual(m['console_storage']['ROUTES'],m['console_storage']['BASE']+416)
            self.assertEqual(m['console_storage']['BYTES'],880)
            self.assertEqual(m['console_storage']['BITMAP'],m['console_storage']['BASE']+868)
            self.assertEqual(m['console_storage']['KEYMAP']+128,generate_tasks.storage(m)['BASE']+0xf30)
            for failure in ('overlap','overflow'):
                bad=copy.deepcopy(m)
                if failure=='overlap':bad['profile']['code_origin']=m['console_storage']['BASE']
                else:bad['profile']['code_origin']=(bank<<16)+0xff80
                with self.subTest(bank=bank,failure=failure),self.assertRaises(ValueError):console.reserve_metadata(bad)

if __name__=='__main__':unittest.main()
