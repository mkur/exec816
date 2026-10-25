import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from measure_fastbasic_responsive import fixture_source,lexical


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


if __name__=='__main__':unittest.main()
