import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_list_loading import partition
from sio_transaction_trace import BASE_HZ


class ListLoadingMeasurementTests(unittest.TestCase):
    def test_direct_partition_excludes_nested_and_other_task_calls(self):
        sites = {'read': dict(caller='load', callee='read'),
                 'take': dict(caller='read', callee='take')}
        parent = dict(begin=0, end=100, dp=0x1000)
        rows = [dict(kind='read', begin=10, end=60, dp=0x1000),
                dict(kind='take', begin=20, end=40, dp=0x1000),
                dict(kind='read', begin=30, end=50, dp=0x1100)]
        result = partition(parent, rows, sites, 'load')
        self.assertEqual(result['counts'], {'read': 1})
        self.assertAlmostEqual(result['parts_ms']['read'], 50/BASE_HZ*1000)
        self.assertAlmostEqual(sum(result['parts_ms'].values()), result['total_ms'])

    def test_repeated_call_sites_aggregate_by_callee(self):
        sites = {k:dict(caller='load', callee='patch') for k in ('preflight', 'apply')}
        rows = [dict(kind='preflight', begin=10, end=30, dp=0x1000),
                dict(kind='apply', begin=50, end=80, dp=0x1000)]
        result = partition(dict(begin=0, end=100, dp=0x1000), rows, sites, 'load')
        self.assertEqual(result['counts'], {'patch': 2})
        self.assertAlmostEqual(result['parts_ms']['patch'], 50/BASE_HZ*1000)
        self.assertAlmostEqual(sum(result['parts_ms'].values()), result['total_ms'])

    def test_overlapping_direct_calls_rejected(self):
        sites = {'read': dict(caller='load', callee='read')}
        rows = [dict(kind='read', begin=10, end=60, dp=0x1000),
                dict(kind='read', begin=50, end=80, dp=0x1000)]
        with self.assertRaisesRegex(RuntimeError, 'Overlapping'):
            partition(dict(begin=0, end=100, dp=0x1000), rows, sites, 'load')


if __name__ == '__main__':
    unittest.main()
