"""Independent directory-row and preempted observation controls."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from measure_spartados_listing import directory_rows, spans, in_clock_window


def event(tick, pc, dp):
    return tick, ['cpu', '0', '0', '8', f'{pc:x}', '0', '0', '0', '0', f'{dp:x}']


class ListingMeasurementTests(unittest.TestCase):
    def test_bridge_clock_matches_unwrapped_observer_and_crosses_rollover(self):
        period = 1 << 32
        self.assertTrue(in_clock_window(dict(begin=period+110, end=period+150), 100, 200))
        self.assertTrue(in_clock_window(dict(begin=period-50, end=period+50), period-100, 100))
        self.assertFalse(in_clock_window(dict(begin=period+50, end=period+90), 100, 200))

    def test_same_routine_in_two_tasks_is_paired_by_direct_page(self):
        rows = spans([event(0, 100, 0xd00), event(10, 100, 0xe00),
                      event(20, 101, 0xe00), event(30, 101, 0xd00)],
                     {'write': dict(entry=100, returns=[101])})
        self.assertEqual([(r['dp'], r['begin'], r['end']) for r in rows],
                         [(0xe00, 10, 20), (0xd00, 0, 30)])

    def test_missing_return_rejects_truncated_measurement(self):
        with self.assertRaisesRegex(RuntimeError, 'Unfinished'):
            spans([event(0, 100, 0xd00)], {'command': dict(entry=100, returns=[101])})

    def test_imported_tail_jump_counts_entries_without_fabricating_returns(self):
        rows = spans([event(0, 100, 0xd00), event(10, 100, 0xd00)],
                     {'write': dict(entry=100, returns=[])})
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['entry_only'] for r in rows))

    def test_same_task_reentry_rejects_ambiguous_measurement(self):
        with self.assertRaisesRegex(RuntimeError, 'Nested'):
            spans([event(0, 100, 0xd00), event(10, 100, 0xd00)],
                  {'command': dict(entry=100, returns=[101])})

    def test_uniform_512_byte_media_and_directory_record_crossing(self):
        # Uniform 512-byte ATR, map in sector 2, records in sectors 3 and 4.
        # Row 22 crosses the sector boundary; no short boot sectors are present.
        raw = bytearray(16+4*512)
        struct.pack_into('<HHHH', raw, 0, 0x296, 4*512//16, 512, 0)
        struct.pack_into('<H', raw, 16+9, 2)
        struct.pack_into('<HH', raw, 16+512+4, 3, 4)
        data = bytearray(1024)
        data[3:6] = (25*23).to_bytes(3, 'little')
        for i in range(24):
            pos = (i+1)*23
            data[pos] = 8
            data[pos+3:pos+6] = (i*12345).to_bytes(3, 'little')
            data[pos+6:pos+17] = f'F{i:07d}TXT'.encode()
        raw[16+2*512:] = data
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'disk.atr'
            path.write_bytes(raw)
            rows = directory_rows(path, '')
            self.assertEqual(len(rows), 24)
            self.assertEqual(rows[21]['name'], 'F0000021.TXT')
            self.assertEqual(rows[21]['bytes'], 21*12345)
            # Deleted rows are skipped without changing the remaining order.
            raw[16+2*512+22*23] |= 16
            path.write_bytes(raw)
            rows = directory_rows(path, '')
            self.assertEqual(len(rows), 23)
            self.assertEqual(rows[21]['name'], 'F0000022.TXT')


if __name__ == '__main__':
    unittest.main()
