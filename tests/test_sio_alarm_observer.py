import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from sio_concurrent_trace import alarm_observations

def edge(t,channel):return (t,['timer',str(t),str(channel)])
def mask(t,value):return (t,['register',str(t),'14',str(value)])
class AlarmObserverTests(unittest.TestCase):
    def test_rom_temporary_enable_is_cancelled(self):
        events=[mask(9,0xdf),edge(10,0),mask(11,0xe2),mask(50,0xc2),mask(51,0xe2)]
        self.assertEqual(alarm_observations(events,[],[1000],1000,0),([],[1],[]))
    def test_acknowledgement_does_not_hide_a_late_handler(self):
        events=[edge(10,1),mask(11,0xe0),mask(12,0xe2)]
        self.assertEqual(alarm_observations(events,[211],[1000],1000,1),([201],[],[]))
    def test_cancelled_edge_still_has_a_measurable_deadline(self):
        events=[edge(10,1),mask(211,0xe0)]
        self.assertEqual(alarm_observations(events,[],[1000],1000,1),([],[201],[]))
    def test_unserviced_edge_remains_visible(self):
        self.assertEqual(alarm_observations([edge(10,1)],[],[1000],1000,1),([],[],[990]))
if __name__=='__main__':unittest.main()
