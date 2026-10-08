import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_mouse_acceleration import gains,files,metadata
from mouse_acceleration_oracle import AXIS,DIAGONAL,cases
from desktop_mouse import slow_schedule,coordinates


class MouseAccelerationTests(unittest.TestCase):
    def test_generated_curve_matches_contract(self):
        for path,source in files().items():
            self.assertEqual(path.read_text(),source)
        table=gains()
        for column,offset in ((AXIS,0),(DIAGONAL,32)):
            self.assertEqual(table[offset:offset+17],[int(v*4) for v in column])
        self.assertGreater(len(cases()),2500)

    def test_physical_packets_reach_exact_mild_targets(self):
        class Controller:
            def __init__(self,position):self.position=list(position)
            def _cmd_ok(self,command):
                _,_,delay,dx,dy,_=command.split()
                self_delay=int(delay)
                self.test_delay=self_delay
                for i,raw in enumerate((dx,dy)):
                    steps=int(raw)//16
                    distance=abs(steps)
                    assert abs(steps)<=2
                    self.position[i]+=distance*(1 if steps>=0 else -1)
        p={'build':{'desktop_mouse':metadata('mild')}}
        for start,target in [((320,120),(584,160)),((639,239),(0,0)),((0,0),(639,239)),
                             ((638,238),(639,239)),((350,150),(349,147))]:
            with self.subTest(start=start,target=target):
                b=Controller(start)
                self.assertEqual(slow_schedule(b,p,start,target),list(target))
                self.assertEqual(b.position,list(target))

    def test_off_uses_pixel_edges(self):
        p={'build':{'desktop_mouse':metadata('off')}}
        self.assertEqual(coordinates(p,[639,239],[638,238]),([637,237],[-1,-1]))
        self.assertEqual(coordinates(p,[320,120],[639,239]),([639,239],[160,60]))
