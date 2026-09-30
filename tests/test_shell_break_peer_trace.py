import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from shell_break_peer_trace import continuous_gaps
from sio_transaction_trace import BASE_HZ


class PeerSectorDeadlineTests(unittest.TestCase):
    def test_ignores_idle_time_outside_continuous_read(self):
        tick=BASE_HZ/1000
        gaps=continuous_gaps([361,10,11,12,361],
                            [0,1000*tick,1100*tick,1200*tick,3000*tick],
                            [10*tick,1050*tick,1150*tick,1250*tick,3100*tick],
                            [10,11,12])
        self.assertEqual(gaps,[50000,50000])

    def test_rejects_late_or_missing_sector(self):
        tick=BASE_HZ/1000
        for sectors,starts,posts in [([10,11,12],[0,250*tick,300*tick],[tick,260*tick,310*tick]),
                                     ([10,12],[0,10*tick],[tick,11*tick]),
                                     ([10,11,12],[0,10*tick],[tick,11*tick])]:
            with self.assertRaises(RuntimeError):
                continuous_gaps(sectors,starts,posts,[10,11,12])
