import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_sector_copy import samples, summarize, hello_samples, BASE_HZ


MARKS = dict(consume=100, loop=200, bookkeeping=300, return0=400, return1=410,
             native_nmi=500, native_irq=600)


def cpu(tick, pc, dp=0x2200, p=0):
    event = ['cpu']+['0']*11
    event[4], event[9], event[11] = f'{pc:x}', f'{dp:x}', f'{p:x}'
    return tick, event


def activation(start=0):
    return [cpu(start,100), cpu(start+10,200), cpu(start+20,200),
            cpu(start+30,200), cpu(start+40,300), cpu(start+50,400)]


class SectorCopyMeasurementTests(unittest.TestCase):
    def test_counts_final_loop_test_and_partitions_complete_routine(self):
        row = samples(activation(), MARKS)[0]
        self.assertEqual(row['bytes'], 2)
        self.assertEqual(row['end'], 50.75)
        self.assertAlmostEqual(row['microseconds']['loop'], 30/BASE_HZ*1e6)
        self.assertAlmostEqual(sum(row['microseconds'][k] for k in ('setup','loop','bookkeeping')),
                               row['microseconds']['total'])

    def test_interrupts_exclude_whole_activation_but_preserve_elapsed_sample(self):
        interrupted = activation(100)
        interrupted.insert(2, cpu(115,500,dp=0))
        interrupted.insert(3, cpu(116,600,dp=0))
        rows = samples(activation()+interrupted, MARKS)
        self.assertEqual(rows[1]['interrupts'], 2)
        summary = summarize(rows)
        self.assertEqual((summary['samples'],summary['uninterrupted'],summary['interrupted']), (2,1,1))
        self.assertEqual(summary['uninterrupted_us']['total']['mean_us'], rows[0]['microseconds']['total'])

    def test_rejects_truncated_or_wrong_domain_trace(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            samples(activation()[:-1], MARKS)
        wrong = activation()
        wrong[2] = cpu(20,200,dp=0x2400)
        with self.assertRaisesRegex(RuntimeError, 'domain'):
            samples(wrong, MARKS)

    def test_rejects_masked_measurement_and_no_uninterrupted_baseline(self):
        masked = activation()
        masked[0] = cpu(0,100,p=4)
        with self.assertRaisesRegex(RuntimeError, 'masked'):
            samples(masked, MARKS)
        events = activation()
        events.insert(1,cpu(5,500))
        with self.assertRaisesRegex(RuntimeError, 'No uninterrupted'):
            summarize(samples(events, MARKS))

    def test_hardware_window_excludes_directory_consumption(self):
        events = []
        for index,sector in enumerate([69,*range(70,89),3]):
            events.append((index*100,['command','0','1']))
            events.extend((index*100+n+1,['ready','0',str(byte)]) for n,byte in enumerate([49,82,sector,0,0]))
        rows = [dict(begin=10,bytes=23)]+[dict(begin=index*100+50,bytes=128 if index<19 else 55) for index in range(1,20)]+[dict(begin=2050,bytes=23)]
        self.assertEqual(hello_samples(events, rows), rows[1:-1])
        rows[10]['bytes'] = 127
        with self.assertRaisesRegex(RuntimeError, 'consume sequence'):
            hello_samples(events, rows)
