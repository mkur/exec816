"""Measurement boundaries must exclude setup and accept tail-called C helpers."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gem_text_trace import summarize


class TextTrace(unittest.TestCase):
    def trace(self, events):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.log'
            path.write_text(''.join(f'[SIOTXN] cpu {tick} 0 8 {pc:x}\n' for tick,pc in events))
            return summarize(path, {'measure':{'entry':1,'returns':[2]},
                                    'submit':{'entry':3,'returns':[]},
                                    'idle':{'entry':4,'returns':[5]}})

    def test_only_complete_measured_work_is_counted(self):
        cases=self.trace([(0,3),(10,1),(20,3),(25,3),(30,4),(40,5),(50,2),(60,3)])
        self.assertEqual(len(cases),1)
        self.assertEqual(cases[0]['entries'],{'measure':1,'submit':2,'idle':1})
        self.assertEqual(cases[0]['routines']['idle']['calls'],1)
        self.assertEqual((cases[0]['start'],cases[0]['end']),(10,50))

    def test_partial_or_overlapping_measurement_is_rejected(self):
        for events in ([(10,1)],[(10,1),(20,1)],[(10,1),(20,4),(30,2)]):
            with self.subTest(events=events),self.assertRaises(RuntimeError):self.trace(events)
