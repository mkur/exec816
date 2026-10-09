"""The generated run representation must preserve every source pixel."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from extract_gem_aes import alert_icons

class AlertIcons(unittest.TestCase):
    def test_runs_preserve_rows_edges_and_gaps(self):
        masks={name:[0x8001,0x8001,0xffff,0xffff,0,0,0xaaaa,0x5555]*8
               for name in ('NOTE','QUEST','STOP')}
        offsets,runs=alert_icons('ALERT_ICONS='+repr(masks))
        for index,words in enumerate(masks.values()):
            pixels=set()
            for at in range(offsets[index],offsets[index+1],3):
                y,x,width=runs[at:at+3]
                self.assertGreater(width,0);self.assertLessEqual(x+width,32)
                for xx in range(x,x+width):
                    self.assertNotIn((xx,y),pixels);pixels.add((xx,y))
            expected={(x,y) for y in range(32) for x in range(32)
                      if words[y*2+x//16] & (0x8000>>(x%16))}
            self.assertEqual(pixels,expected)
