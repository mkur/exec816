import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from menu_response_observer import endpoint, heading_at, pixels_match, pointer_response
from sio_transaction_trace import BASE_HZ


class MenuResponseObserver(unittest.TestCase):
    headings = [dict(index=0, enabled=True, bounds=[128,0,192,11]),
                dict(index=1, enabled=True, bounds=[208,0,272,11]),
                dict(index=2, enabled=False, bounds=[272,0,320,11])]

    def response(self, changes):
        names = {'x':1, 'y':2, 'route':3, 'loss':4}
        events = [(t,['cpu',str(t),'0','8',f'{names[n]:x}',f'{a:x}',
                      '0','0','1000','800','0','0']) for t,n,a in changes]
        sample = dict(heading=1, initial_pointer=[160,8], headings=self.headings,
                      complete_frame=dict(last_nonmatch=80, first_match=100))
        return pointer_response(events, {1:'pointer_x',2:'pointer_y',
            3:'heading_routed',4:'AESMOUSE_LOST'}, sample, 0, 120, 0x800)

    def test_half_open_enabled_hit_bounds(self):
        for x,y,want in ((191,8,0),(192,8,None),(208,8,1),(272,8,None),
                         (224,11,None),(224,-1,None)):
            self.assertEqual(heading_at(x,y,self.headings),want)

    def test_fresh_crossing_precedes_deferred_routing(self):
        r=self.response([(10,'x',224),(11,'y',8),(45,'route',1)])
        self.assertTrue(r['available'])
        self.assertAlmostEqual(r['travel_ms'],11*1000/BASE_HZ)
        self.assertAlmostEqual(r['crossing_to_routing_ms'],34*1000/BASE_HZ)
        self.assertEqual(r['crossing_to_visible_ms'],[69*1000/BASE_HZ,89*1000/BASE_HZ])

    def test_routing_alone_is_not_a_crossing(self):
        self.assertFalse(self.response([(45,'route',1)])['available'])

    def test_recrossing_and_loss_are_not_clean_samples(self):
        prefix=[(10,'x',224),(11,'y',8),(45,'route',1)]
        for suffix in ([(50,'loss',0)],[(50,'x',160),(51,'y',8),
                                       (60,'x',224),(61,'y',8)]):
            self.assertFalse(self.response(prefix+suffix)['available'])

    def test_frame_ticks_wrap(self):
        start=(1<<32)-10
        self.assertEqual(endpoint(start,15),(1<<32)+15)
        self.assertEqual(endpoint(start+(1<<32),15),(2<<32)+15)

    def test_popup_equality_does_not_imply_title_equality(self):
        area=(0,0,40,30);want=bytes(40*30*4);got=bytearray(want)
        got[2*40*4+4:2*40*4+8]=b'xxxx'
        self.assertTrue(pixels_match(got[11*40*4:],want[11*40*4:],(0,11,40,30)))
        self.assertFalse(pixels_match(got,want,area))
        self.assertTrue(pixels_match(got,want,area,[(0,0)]))
        self.assertFalse(pixels_match(got,want,area,[(20,0)]))
        # A bottom-rule error outside the cursor cannot be hidden by masking.
        got[10*40*4+30*4]=1
        self.assertFalse(pixels_match(got,want,area,[(0,0)]))
