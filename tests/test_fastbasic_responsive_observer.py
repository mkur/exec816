import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from measure_fastbasic_responsive import fixture_source,lexical,readiness,BASE_HZ


class ResponsiveObserverTests(unittest.TestCase):
    def test_maximum_fixture_leaves_one_byte_for_an_accepted_edit(self):
        data=fixture_source()
        self.assertEqual(len(data),32767)
        self.assertLessEqual(max(map(len,data.split(b'\n'))),255)
        self.assertGreater(len(data.split(b'\n')),80)
        self.assertEqual(data.split(b'\n')[0],b'alphaq')
        self.assertNotIn(b'\t',data)

    def test_independent_syntax_colours_cover_quotes_comments_and_keywords(self):
        self.assertEqual(lexical(b'PRINT "REM"'),[4]*5+[1]+[2]*5)
        self.assertEqual(lexical(b"x ' PRINT"),[1,1]+[3]*7)
        self.assertEqual(lexical(b'REM "PRINT"'),[3]*11)
        self.assertEqual(lexical(b'PRINTED'),[1]*7)

    def test_dispatch_can_follow_completed_scanout(self):
        sample=dict(started_clock=100,model_clock=200,observation_end_clock=250,
            dispatch_observation_end_clock=400,input_ready_ms=None,scanout_ms=150,
            operation='append')
        event=['cpu','300','4','8','001234','0','0','0','0','1100']
        record=readiness(dict(task_dp=0x1100,samples=[sample]),[(300.5,event)],0x1234)
        self.assertAlmostEqual(record['samples'][0]['input_ready_ms'],200.5*1000/BASE_HZ)


if __name__=='__main__':unittest.main()
