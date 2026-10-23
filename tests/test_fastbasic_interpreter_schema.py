import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_fastbasic_interpreter import products


class InterpreterContractTests(unittest.TestCase):
    def test_generated_contract_is_current(self):
        for path,text in products().items():
            self.assertEqual(path.read_text(),text,str(path))

    def test_records_fit_shared_wire_layout(self):
        a=json.loads((ROOT/'abi/fastbasic-interpreter.json').read_text())
        self.assertEqual(a['source']['bytes'],28)
        self.assertEqual(a['result']['fields']['message']+a['message_capacity'],a['result']['bytes'])
        self.assertEqual(a['capability']['fields']['reserved']+2,a['capability']['bytes'])
        self.assertEqual(sorted(a['source']['fields'].values()),[0,2,4,8,12,16,20,24])

    def test_new_services_fit_existing_guest_aperture(self):
        a=json.loads((ROOT/'abi/fastbasic.json').read_text())
        services=a['services']
        self.assertEqual(list(services)[-2:],['SOURCE','SOURCE_RESULT'])
        self.assertLessEqual(a['service_base']+len(services)*a['service_stride'],0xfa00)


if __name__=='__main__':unittest.main()
