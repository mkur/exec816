import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from make_data_disk import make
from sector_images import ATRImage
class DataDisk(unittest.TestCase):
    def test_sdfs_byte_readback_and_text_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            temp=Path(directory);source=temp/'source';(source/'TOOLS').mkdir(parents=True)
            (source/'TEXT.TXT').write_bytes(b'one\r\ntwo\rthree\n')
            binary=bytes(range(256))*2+b'\x9b\r\n';(source/'TOOLS'/'TEST.BIN').write_bytes(binary)
            expected={'TEXT.TXT':b'one\ntwo\nthree\n','TOOLS/TEST.BIN':binary}
            for size in (128,256,512):
                first=temp/f'first-{size}.atr';second=temp/f'second-{size}.atr'
                self.assertEqual(make(first,source,{'TOOLS/TEST.BIN'},size),expected)
                make(second,source,{'TOOLS/TEST.BIN'},size)
                self.assertEqual(first.read_bytes(),second.read_bytes())
                proof=json.loads(first.with_suffix('.verification.json').read_text())
                self.assertEqual(set(proof['files']),set(expected));self.assertEqual(proof['sector_bytes'],size)
    def test_mydos_option_and_bad_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(source/'A.TXT').write_text('a\n')
            self.assertEqual(make(root/'mydos.atr',source,filesystem='mydos'),{'A.TXT':b'a\n'})
            for options in ({'sector_bytes':1024},{'sector_bytes':512,'filesystem':'mydos'},{'filesystem':'unknown'}):
                with self.assertRaises(ValueError):make(root/'bad.atr',source,**options)
    def test_sdfs_labels_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir()
            for size,label in ((128,'SYS'),(256,'WORK'),(512,'ABCDEFGH')):
                image=root/f'{size}.atr'
                make(image,source,sector_bytes=size,label=label)
                self.assertEqual(bytes(ATRImage(image.read_bytes()).sector(1)[22:30]),
                                 label.ljust(8).encode('ascii'))
if __name__=='__main__':unittest.main()
