import hashlib
from pathlib import Path
import sys,tempfile,unittest,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from package_desktop_preview import package

class DesktopPackage(unittest.TestCase):
    def archive(self,path,boot,extra=None,tamper=False):
        files={'Exec-of816.xex':boot,'system.atr':boot+b'disk','work.atr':b'work',
               'altirraos-816.rom':b'ROM','README.txt':b'Guide','OF816-LICENSE.txt':b'License'}
        if extra:files.update(extra)
        sums=''.join(f'{hashlib.sha256(b).hexdigest()}  {n}\n' for n,b in files.items()).encode()
        if tamper:files['system.atr']=b'wrong disk'
        with zipfile.ZipFile(path,'w') as z:
            for name,data in {**files,'SHA256SUMS':sums}.items():z.writestr('exec816-demo/'+name,data)

    def test_separate_boot_and_matching_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.archive(d/'std.zip',b'standard');self.archive(d/'desk.zip',b'desktop')
            result=package(d/'std.zip',d/'desk.zip',d/'final.zip')
            with zipfile.ZipFile(d/'final.zip') as z:
                self.assertEqual(z.read('exec816-demo/Exec-of816.xex'),b'standard')
                self.assertEqual(z.read('exec816-demo/desktop/Exec-of816.xex'),b'desktop')
                self.assertEqual(z.read('exec816-demo/desktop/system.atr'),b'desktopdisk')
                for name,digest in result['members'].items():
                    self.assertEqual(hashlib.sha256(z.read('exec816-demo/'+name)).hexdigest(),digest)

    def test_changed_media_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.archive(d/'std.zip',b'std');self.archive(d/'desk.zip',b'desk',tamper=True)
            with self.assertRaisesRegex(ValueError,'Changed distribution'):package(d/'std.zip',d/'desk.zip',d/'out.zip')

    def test_build_intermediate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.archive(d/'std.zip',b'std');self.archive(d/'desk.zip',b'desk',{'build.json':b'{}'})
            with self.assertRaisesRegex(ValueError,'Build intermediate'):package(d/'std.zip',d/'desk.zip',d/'out.zip')
