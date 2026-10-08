"""Check the donor calculator's generated geometry and bounded resource inputs."""
import json,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_calculator import prepare,resource_cases


class CalculatorResource(unittest.TestCase):
    def test_resource(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);record=prepare(out);raw=(out/'CALC.RSC').read_bytes()
            header=struct.unpack_from('>18H',raw)
            self.assertEqual((header[0],header[10],header[11],header[12]),(0,21,1,1))
            objects=[struct.unpack_from('>hhhHHHIhhhh',raw,header[1]+i*24) for i in range(21)]
            self.assertEqual(objects[0][9:11],(23,20))
            for row in objects:
                self.assertEqual(row[4]&~(1|2|4|16|32|128),0)
            for row in objects[1:]:
                self.assertGreaterEqual(row[7],0);self.assertGreaterEqual(row[8],0)
                self.assertLessEqual(row[7]+row[9],23);self.assertLessEqual(row[8]+row[10],20)
            self.assertEqual((objects[2][3],objects[2][6]),(22,header[2]))
            ted=struct.unpack_from('>III8h',raw,header[2])
            self.assertEqual(raw[ted[0]:ted[0]+12],b' '*11+b'\0')
            self.assertEqual((ted[3],ted[5],ted[8],ted[9],ted[10]),(3,1,-1,0,0))
            ids=(out/'source/src/apps/calcrsc.h').read_text()
            self.assertRegex(ids,r'#define CEQ\s+19');self.assertRegex(ids,r'#define CQUIT\s+20')
            self.assertEqual(record,prepare(out))
            self.assertEqual(len(resource_cases(out)),5)
