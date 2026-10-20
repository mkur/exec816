import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from generate_fastbasic_diagnostics import files

class FastBasicDiagnosticsTests(unittest.TestCase):
    def test_generated_public_contract(self):
        for path,expected in files().items():
            self.assertEqual(path.read_text(),expected,str(path))

    def test_record_extents_and_registration(self):
        a=json.loads((ROOT/'abi/fastbasic-diagnostics.json').read_text())
        self.assertEqual(a['fields']['source']+a['source_capacity'],a['fields']['message'])
        self.assertEqual(a['fields']['message']+a['message_capacity'],a['bytes'])
        self.assertEqual(a['fields']['source'],32)
        self.assertEqual(a['bytes'],224)
        self.assertEqual(a['registration_words']['source_pointer'],6)
        self.assertEqual(a['registration_words']['diagnostic_pointer'],7)
        self.assertEqual(a['registration_words']['job_pointer'],8)
        self.assertEqual(sorted(a['registration_words'].values()),list(range(9)))

if __name__=='__main__':unittest.main()
