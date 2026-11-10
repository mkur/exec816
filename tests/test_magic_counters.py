import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_magic_counters import parse_counter, digit_pixels, verify_capture


def counter_log(instance):
    window, app = instance, instance+1
    x,y = (49,83) if instance==1 else (361,211)
    lines = [f'instance={instance}']
    for count in range(7):
        work = '0,0,0,0' if count==0 else f'{x},{y},230,44'
        paints = count+1 if count else 0
        lines.append(f'count={count} paints={paints} id={app} window={window} top=2 work={work}')
    return '\r\n'.join(lines)+'\r\n'


class MagicCounterTests(unittest.TestCase):
    def test_independent_progress_and_inactive_painting_are_retained(self):
        first = parse_counter(counter_log(1),1)
        second = parse_counter(counter_log(2),2)
        self.assertEqual([row['count'] for row in first],list(range(7)))
        self.assertNotEqual(first[-1]['app'],second[-1]['app'])
        self.assertNotEqual(first[-1]['window'],first[-1]['top'])

    def test_truncated_stalled_and_retired_counter_runs_fail(self):
        original = counter_log(1)
        invalid = [original.replace('instance=1','instance=2'),
            original.replace('count=3','count=2'),
            original.replace('paints=4','paints=3'),
            original.replace('id=2','id=4',1),
            original.replace('work=49,83','work=50,83',1),
            original+'exit=0 count=7 paints=8\n',
            original[:original.index('count=3')]]
        for source in invalid:
            with self.subTest(source=source[:80]),self.assertRaises(ValueError):
                parse_counter(source,1)

    def test_digit_crop_reads_only_the_visible_digits_in_msb_first_order(self):
        frame = bytearray(32000)
        work = [49,83,230,44]
        x,y = work[0]+64,work[1]+8
        frame[y*80+x//8] |= 1 << (7-x%8)
        frame[0] = 255
        pixels = digit_pixels(frame,work)
        self.assertEqual(len(pixels),48*8)
        self.assertEqual(pixels[0],1)
        self.assertEqual(sum(pixels),1)
        with self.assertRaises(ValueError):
            digit_pixels(frame[:-1],work)
        with self.assertRaises(ValueError):
            digit_pixels(frame,[600,83,230,44])

    def test_logs_alone_do_not_prove_both_visible_counters_updated(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root/'capture'
            capture.mkdir()
            (capture/'LAUNCH.LOG').write_text('magic=1 launcher=0\nfirst=2 second=3\n')
            for instance in (1,2):
                (capture/f'COUNT{instance}.LOG').write_text(counter_log(instance))
            for name in ('first','second'):
                (capture/(name+'.png')).write_bytes(b'fixture')
                (capture/(name+'.bin')).write_bytes(bytes(32000))
            with self.assertRaisesRegex(ValueError,'digits did not change'):
                verify_capture(root)
            frame = bytearray(32000)
            for instance in (1,2):
                work = parse_counter(counter_log(instance),instance)[-1]['work']
                x,y = work[0]+64,work[1]+8
                frame[y*80+x//8] |= 1 << (7-x%8)
            (capture/'second.bin').write_bytes(frame)
            result = verify_capture(root)
            self.assertEqual(result['status'],'pass')
            self.assertEqual([case['digit_pixels_changed'] for case in result['counters']],[1,1])


if __name__ == '__main__':
    unittest.main()
