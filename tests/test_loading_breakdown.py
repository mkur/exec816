import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_loading_breakdown import checksum, direct_partition, ms, partition_packet, payload_partition


def packet(sector=70, begin=0):
    command = [49, 82, sector & 255, sector >> 8]
    command.append(checksum(command))
    payload = list(range(128))
    payload.append(checksum(payload))
    return dict(begin=begin, tx=[(begin+1000+i*300, value, 30) for i,value in enumerate(command)],
                releases=[begin+3000], idle=[begin+2500],
                rx=[(begin+4000,65,31), (begin+8000,67,31)]+
                   [(begin+9000+i*311,value,31) for i,value in enumerate(payload)])


def events_for(p):
    events = [(p['begin'], ['command','0','1']), (p['releases'][0], ['command','0','0']),
              (p['idle'][0], ['idle','0'])]
    for name, field in (('ready','tx'), ('rxstart','rx')):
        events.extend((t, [name,'0',str(value),str(bit)]) for t,value,bit in p[field])
    return sorted(events)


class LoadingBreakdownTests(unittest.TestCase):
    def test_wire_wait_and_byte_gaps_reconcile(self):
        row = partition_packet(packet())
        self.assertAlmostEqual(sum(row['parts_ms'].values()), row['milliseconds'])
        self.assertAlmostEqual(row['parts_ms']['device_wait'], ms(8000-4310))
        self.assertAlmostEqual(row['parts_ms']['data_byte_gaps'], ms(128))
        self.assertEqual(row['parts_ms']['command_byte_gaps'], 0)

    def test_rejects_truncated_bad_checksum_and_changed_baud(self):
        p = packet()
        p['rx'].pop()
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            partition_packet(p)
        p = packet()
        p['rx'][-1] = (p['rx'][-1][0], 99, 31)
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            partition_packet(p)
        p = packet()
        p['rx'][-1] = (*p['rx'][-1][:2], 32)
        with self.assertRaisesRegex(RuntimeError, 'baud'):
            partition_packet(p)

    def test_rejects_overlapping_bytes_and_wrong_tx_end(self):
        p = packet()
        p['rx'][3] = (p['rx'][2][0]+309, *p['rx'][3][1:])
        with self.assertRaisesRegex(RuntimeError, 'Overlapping'):
            partition_packet(p)
        p = packet()
        p['idle'][0] -= 1
        with self.assertRaisesRegex(RuntimeError, 'TX end'):
            partition_packet(p)

    def test_payload_counts_map_and_partitions_edges_and_intersector_work(self):
        events = sum((events_for(packet(sector,100+60000*i)) for i,sector in enumerate(range(69,89))), [])
        # A following directory read is outside the payload, even when traced.
        events += events_for(packet(3,1300000))
        row = payload_partition(events, 0, 1200000)
        self.assertEqual(row['transfers'], 20)
        self.assertEqual(row['wire_bytes'], 2720)
        self.assertEqual(len(row['gaps_ms']), 19)
        self.assertAlmostEqual(sum(row['parts_ms'].values()), ms(1200000))
        self.assertAlmostEqual(row['parts_ms']['before_first_command'], ms(100))
        with self.assertRaisesRegex(RuntimeError, 'sector sequence'):
            payload_partition(events, 60000, 1200000)
        with self.assertRaisesRegex(RuntimeError, 'before checksum'):
            payload_partition(events, 0, 1141000)

    def test_loader_partition_does_not_double_count_nested_calls(self):
        calls = [dict(site='load_before_validate0',begin=10,end=60),
                 dict(site='validate_before_parse0',begin=20,end=50),
                 dict(site='load_before_copy0',begin=70,end=90)]
        parent = dict(begin=0,end=100)
        result = direct_partition(calls,parent,'load')
        self.assertEqual(len(result['parts_ms']), 3)
        self.assertAlmostEqual(result['parts_ms']['caller_instructions'], ms(30))
        self.assertAlmostEqual(sum(result['parts_ms'].values()), ms(100))
        broken = copy.deepcopy(calls)
        broken[2]['begin'] = 55
        with self.assertRaisesRegex(RuntimeError, 'Overlapping'):
            direct_partition(broken,parent,'load')

    def test_repeated_direct_calls_are_aggregated_with_counts(self):
        calls = [dict(site='load_before_read0',begin=10,end=30),
                 dict(site='load_before_read0',begin=50,end=80)]
        result = direct_partition(calls,dict(begin=0,end=100),'load')
        self.assertEqual(result['counts']['load_before_read0'], 2)
        self.assertAlmostEqual(result['parts_ms']['load_before_read0'], ms(50))


if __name__ == '__main__':
    unittest.main()
