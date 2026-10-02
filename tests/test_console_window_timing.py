"""Negative controls for the multiwindow development timing gates."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import test_console_fairness as fixture
from sio_transaction_trace import BASE_HZ

class WindowTimingTests(unittest.TestCase):
    def observations(self):
        points={
            'input_capture':[30000,40000,45000,70000],
            'small_begin':[14000+i*1000 for i in range(8)],
            'small_collected':[14500+i*1000 for i in range(8)],
            'small_visible':[14700+i*1000 for i in range(8)],
            'flood_begin':[i*1000 for i in range(16)],
            'flood_collected':[500+i*1000 for i in range(16)],
            'third_collected':[32000],'third_visible':[34000],
            'echo_visible':[50000],'break_durable':[72000],
            'read_begin':[0],'read_end':[100000],
            'sio_start':[0,3000,11000],'signal_post':[1000,4000,13000],
        }
        return points

    def analyze(self,points):
        marks={name:i+1 for i,name in enumerate(points)}
        events=sorted((tick,['cpu','0','0','0',f'{marks[name]:x}']) for name,ticks in points.items() for tick in ticks)
        with patch.object(fixture,'wire_timing',return_value={'verdict':'pass','violations':[]}),patch.object(fixture,'read_events',return_value=events):
            return fixture.timing(Path('unused.log'),marks,Path('unused.atr'))

    def test_complete_observations(self):
        self.assertEqual(self.analyze(self.observations())['windows']['small_collected_ms']['samples'],8)

    def test_every_window_deadline_rejects_late_completion(self):
        targets={'small_collected_ms':('small_collected',2000),'small_visible_ms':('small_visible',2000),
                 'flood_collected_ms':('flood_collected',2000),'third_collected_ms':('third_collected',10000),
                 'third_visible_ms':('third_visible',10000),'cooked_echo_ms':('echo_visible',30000),
                 'break_durable_ms':('break_durable',70000)}
        for name,(point,start) in targets.items():
            with self.subTest(name=name):
                values=self.observations();values[point][-1]+=int((fixture.LIMITS[name]+1)*BASE_HZ/1000)
                with self.assertRaises(RuntimeError):self.analyze(values)

    def test_missing_or_duplicate_observations_fail(self):
        for name in self.observations():
            if name in ('sio_start','signal_post'):continue
            for duplicate in (False,True):
                with self.subTest(name=name,duplicate=duplicate):
                    values=self.observations()
                    if duplicate:values[name].append(values[name][0])
                    else:values[name].pop(0)
                    with self.assertRaises(RuntimeError):self.analyze(values)

    def test_early_completion_fails(self):
        values=self.observations();values['third_collected']=[9000]
        with self.assertRaises(RuntimeError):self.analyze(values)

    def test_unchanged_serial_next_sector_limit(self):
        values=self.observations();values['sio_start'][1]=400000;values['read_end']=[1000000]
        with self.assertRaises(RuntimeError):self.analyze(values)
