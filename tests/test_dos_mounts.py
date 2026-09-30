import copy,json,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from generate_dos_mounts import validate_mounts,encode,load,select_system
from filesystem_formats import MYDOS,SDFS
from generate_filesystem_formats import generate
class DosMountTests(unittest.TestCase):
    def test_backend_ids_and_small_sdfs_geometry(self):
        generate(check=True)
        self.assertEqual((MYDOS,SDFS),(1,2))
        raw=encode([dict(alias='D1',unit=49,sectors=100,sector_bytes=128,format=SDFS)])
        self.assertEqual(raw[-1],SDFS)
    def test_explicit_geometry_and_layout(self):
        for size,profile in ((128,1),(256,1),(128,2),(128,4),(256,4)):
            m=dict(alias='D1',unit=49,sectors=720,sector_bytes=size,profile=profile)
            raw=encode([m]);self.assertEqual(len(raw),44)
            self.assertEqual(struct.unpack('<32sHHIHBB',raw),(b'D1'+bytes(30),49,profile,720,size,1,1))
        self.assertEqual(load(ROOT/'config/dos-mounts.json'),dict(mounts=[],system_mount=None))
        self.assertEqual(encode([]),b'')
    def test_rejects_ambiguous_or_narrowed_geometry(self):
        seed=dict(alias='D1',unit=49,sectors=720,sector_bytes=128)
        bad=[dict(alias=v) for v in ('','x'*32,'D:','é','../','NIL','nil','Raw','CON','Console','SYS','sys')]
        bad += [dict(unit=v) for v in (True,48,57,65585)]
        bad += [dict(sectors=v) for v in (367,65536,-1,720.0,'720')]
        bad += [dict(sector_bytes=512),dict(sector_bytes=256,profile=2),dict(profile=3),dict(profile=5),dict(boot=0),dict(format=0),dict(extra=1)]
        for patch in bad:
            with self.subTest(patch=patch),self.assertRaises(ValueError):encode([{**seed,**patch}])
        for m in ({**seed,'unit':50,'alias':'d1'},{**seed,'alias':'D2'}):
            with self.assertRaises(ValueError):encode([seed,m])
        for value in (None,{},[seed]*9,[{}],[None]):
            with self.assertRaises(ValueError):validate_mounts(value)
    def test_system_selection(self):
        mounts=validate_mounts([dict(alias='DATA',unit=51,sectors=720,sector_bytes=128),
                                dict(alias='D2',unit=50,sectors=720,sector_bytes=128)])
        self.assertEqual(select_system(mounts),dict(system_slot=255,system_drive=0,allowed_drives=0))
        self.assertEqual(select_system(mounts,'d2'),dict(system_slot=1,system_drive=2,allowed_drives=251))
        for name in ('D1','DATA',False):
            with self.subTest(name=name), self.assertRaises(ValueError):select_system(mounts,name)
        with self.assertRaises(ValueError):select_system([{**mounts[1],'unit':49}], 'D2')
        self.assertEqual(load(ROOT/'config/shell-sdfs.json')['system_mount'],'D1')

    def test_override_conflicts_include_alias_and_unit(self):
        mounts=validate_mounts([dict(alias='D4',unit=51,sectors=720,sector_bytes=128),
                                dict(alias='D1',unit=49,sectors=720,sector_bytes=128)])
        self.assertEqual(select_system(mounts,'D1')['allowed_drives'],243)

    def test_only_explicit_config_key(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mounts.json'
            for value in ([],{},dict(mounts=[],image='test.atr')):
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):load(p)
if __name__=='__main__':unittest.main()
