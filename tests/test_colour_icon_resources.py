import json,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_gem_resource import resource


class ColourIconResource(unittest.TestCase):
    def build_icon(self,selected=False):
        spec=dict(width=16,height=2,label='Twelve chars',pixels=['0123456789abcdef','....0123....4567'])
        if selected:spec['selected_pixels']=['fedcba9876543210','0123........4567']
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'icon.json'
            path.write_text(json.dumps([[[-1,-1,-1,33,32,0,spec,0,0,96,16]]]))
            return resource(path)

    def test_standard_extension_and_planar_pixels(self):
        payload=self.build_icon(True)
        header=struct.unpack_from('>18H',payload)
        self.assertEqual(header[0],4)
        length,table,end=struct.unpack_from('>III',payload,header[17])
        self.assertEqual((length,table,end),(len(payload),header[17]+12,0))
        self.assertEqual(struct.unpack_from('>2I',payload,table),(0,0xffffffff))
        block=table+8;form=block+38+8+12
        self.assertEqual(payload[block+46:form],b'Twelve chars')
        self.assertEqual(struct.unpack_from('>hIIIII',payload,form),(4,0,0,1,0,0))
        pens=(0,15,1,2,4,6,3,5,7,8,9,10,12,14,11,13)
        for selected,expected in ((False,pens),(True,pens[::-1])):
            start=form+22+(20 if selected else 0)
            values=[]
            for x in range(16):
                values.append(sum(1<<p for p in range(4) if payload[start+p*4+x//8]&(128>>(x%8))))
            self.assertEqual(tuple(values),expected)
            self.assertEqual(payload[start+16:start+20],b'\xff\xff'+(b'\xf0\x0f' if selected else b'\x0f\x0f'))
        self.assertEqual(form+22+40,len(payload))

    def test_optional_selected_form_has_no_payload(self):
        payload=self.build_icon()
        classic=struct.unpack_from('>H',payload,34)[0]
        block=classic+12+8;form=block+38+8+12
        self.assertEqual(struct.unpack_from('>I',payload,form+10)[0],0)
        self.assertEqual(form+22+20,len(payload))

    def test_existing_mono_resource_stays_version_zero(self):
        payload=resource(Path(__file__).resolve().parents[1]/'tests/fixtures/application-menu.json')
        self.assertEqual(struct.unpack_from('>H',payload)[0],0)
        self.assertEqual(struct.unpack_from('>H',payload,34)[0],len(payload))


if __name__=='__main__':unittest.main()
