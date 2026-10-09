"""Validate bounded source storage and the shared public native reply ABI."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_memory import ROOT,layout
import generate_native_interrupts as native
import generate_timer_device as timer
import generate_ports as ports
import generate_io as io


class NativeInterruptPackageTests(unittest.TestCase):
    def test_generated_interfaces_and_capacities(self):
        self.assertEqual(native.constants()['SOURCE_CAPACITY'],1)
        self.assertEqual(native.constants()['TEST_SOURCE_CAPACITY'],1)
        self.assertEqual(timer.constants()['COMPLETION_BUDGET'],4)
        self.assertEqual(ports.ABI['native_bindings']['ReplyMsg']['preserved'],['A','X','Y','P','D','DBR','S'])
        for path,text in [
            ('platform/altirraos/native-interrupts.inc',native.assembly()),
            ('platform/altirraos/timer-device.inc',timer.assembly()),
            ('lib/exec/exec-native-ports.inc',ports.native_declarations()),
            ('lib/io/timer-types.inc',timer.types()),
            ('c/include/devices/timer.h',timer.c_header()),
            ('c/include/exec/io.h',io.c_header())]:
            self.assertEqual((ROOT/path).read_text(),text,path)

    def test_no_bank_zero_growth_and_complete_upper_reservations(self):
        for bank in (2,3):
            memory=layout(kernel_bank=bank)
            original=copy.deepcopy(memory)
            with tempfile.TemporaryDirectory() as directory:
                native.generate(directory,0x3f0000,memory)
                timer.generate(directory,0x3f0000,memory)
            for key,value in original.items():
                self.assertEqual(memory[key],value,key)
            n=memory['native_interrupt_storage'];t=memory['timer_device_storage']
            self.assertEqual(n['BYTES']+n['CODE_BYTES']+t['BYTES'],8960)
            self.assertEqual(n['RESERVATION_BYTES'],9728)
            self.assertEqual(n['CODE_BASE']-(t['BASE']+t['BYTES']),768)
            self.assertLessEqual(n['BASE']+n['BYTES'],t['BASE'])
            self.assertLessEqual(t['BASE']+t['BYTES'],n['CODE_BASE'])
            self.assertLessEqual(n['CODE_BASE']+n['CODE_BYTES'],0x400000)

    def test_invalid_budgets_layouts_and_binding_fail(self):
        for generator,mutations in [
            (native,[lambda a:a.update(service_budget=0),lambda a:a.update(service_budget=99),
                     lambda a:a.update(source_capacity=2),lambda a:a['fields'].update(PENDING=3),
                     lambda a:a.update(code_offset=0x5700),lambda a:a.update(state_bytes=32)]),
            (timer,[lambda a:a.update(completion_budget=5),lambda a:a.update(pending_capacity=17),
                    lambda a:a.update(state_bytes=32),lambda a:a['constants'].update(TR_ADDREQUEST=99),
                    lambda a:a['records']['TimerRequest'].update(size=33),
                    lambda a:a['records']['TimerClockRequest']['fields'][1].__setitem__(1,'CARD')]),
            (ports,[lambda a:a['native_bindings']['ReplyMsg']['entry'].update(I=0),
                    lambda a:a['native_bindings']['ReplyMsg']['preserved'].remove('DBR')])]:
            for mutate in mutations:
                abi=copy.deepcopy(generator.ABI);mutate(abi)
                with self.assertRaises(ValueError):generator.constants(abi)
