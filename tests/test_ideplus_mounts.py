import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_dos_mounts import validate_mounts,encode,select_system
class IDEMounts(unittest.TestCase):
    def setUp(self):self.spec=dict(alias='IDE',device='ideplus.device',unit=2,sectors=2000,sector_bytes=512,format=2)
    def test_default_and_wire_identity(self):
        item=validate_mounts([self.spec])[0]
        self.assertEqual(item['profile'],0);self.assertEqual(item['access'],'readonly')
        self.assertEqual(item['boot'],0)
        wire=encode([self.spec]);self.assertEqual(len(wire),46);self.assertEqual(wire[45],1)
        sio=dict(alias='D1',unit=49,sectors=2000,sector_bytes=256)
        self.assertEqual(encode([sio])[45],0)
        self.assertEqual(encode([{**self.spec,'access':'readwrite'}])[44],1)
    def test_operational_limits(self):
        for patch in [dict(unit=0),dict(unit=16),dict(profile=4),dict(sector_bytes=128),dict(sector_bytes=256),dict(boot=1),dict(format=1),dict(sectors=65536)]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate_mounts([{**self.spec,**patch}])
        self.assertEqual(select_system(validate_mounts([self.spec]),'IDE'),
                         dict(system_slot=0,system_drive=0,allowed_drives=0,system_unit=2))
        with self.assertRaises(ValueError):validate_mounts([self.spec,{**self.spec,'alias':'OTHER'}])
if __name__=='__main__':unittest.main()
