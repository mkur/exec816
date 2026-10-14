"""Asset packing checked against the independent procedural frame raster."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_frame_gadgets import NAMES, packed, generate
from gem_render_oracle import Raster, PENS
from test_desktop_presentation import frame


class FrameGadgets(unittest.TestCase):
    def test_packing_matches_existing_frame(self):
        region, data, descriptors = packed()
        raster = Raster(bytes(2048))
        # Vertical gadgets: both arrows, sizer and slider, plus full/closer.
        frame(raster,(20,20,220,200),b'',True,close=True,kind=4|8|32|64|128,slider=(70,30))
        # These rectangles are the tight interiors of the existing marks.
        locations = {'close':(23,22), 'full':(207,22), 'iconify':(191,22),
                     'up':(207,34), 'down':(207,181), 'size':(206,192)}
        for name,(offset,width,height) in zip(NAMES,descriptors):
            for phase in (0,1):
                base=offset+phase*192
                for y in range(height):
                    for x in range(width):
                        byte=data[base+y*16+(x+phase)//2]
                        actual=(byte >> (0 if (x+phase)&1 else 4))&15
                        if name=='tile':
                            expected=15 if x in (0,width-1) or y in (0,height-1) else 12 if y==1 else 0
                        else:
                            left,top=locations[name]
                            expected=raster.pixels[(top+y)*640+left+x]
                        self.assertEqual(actual,expected,(name,phase,x,y))
        self.assertEqual(len(data),2688)
        self.assertEqual(region['reserved_bytes'],4096)

    def test_deterministic_header(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gem-frame-gadgets.h'
            one=generate(p); text=p.read_bytes()
            self.assertEqual(generate(p),one)
            self.assertEqual(p.read_bytes(),text)


if __name__=='__main__':unittest.main()
