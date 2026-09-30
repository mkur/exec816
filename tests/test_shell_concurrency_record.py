import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from shell_concurrency_record import validate


class ShellConcurrencyEvidenceTests(unittest.TestCase):
    def test_qualification_and_corrupted_records(self):
        record = json.loads((ROOT/'docs/qualification/shell-concurrency.json').read_text())
        validate(record)

        def case(r):
            return next(c for c in r['cases'] if c['name'] == 'target256-raw')

        def counts(r):
            return case(r)['case']['counters']

        changes = {
            'missing-mode': lambda r: r['cases'].pop(),
            'shortened-large-read': lambda r: counts(r).update(verified=777),
            'no-command-overlap': lambda r: counts(r).update(commandOverlap=0),
            'missing-key': lambda r: counts(r).update(collected=8),
            'missing-command': lambda r: counts(r).update(commands=4),
            'wrong-output': lambda r: case(r)['case'].update(writes_sha256='wrong'),
            'changed-replay-image': lambda r: case(r)['replay'].update(xex_sha256='different'),
            'changed-replay-input': lambda r: case(r)['replay']['schedule'][0].update(frame=0),
            'lost-task': lambda r: case(r)['case']['observations'][1].update(live=7),
            'touched-reserve': lambda r: case(r)['case']['runtime']['stack_observations'][2].update(untouched_above_floor=-1),
            'enlarged-stack': lambda r: case(r)['case']['runtime']['stack_observations'][0].update(reserved_bytes=2048),
            'late-byte': lambda r: case(r)['timing']['deadline_misses'].update(rx=1),
            'weakened-baud': lambda r: case(r)['timing'].update(rx_byte_deadline_us=80),
            'weakened-alarm': lambda r: r['serial_limits'].update(alarm_lateness_us=200),
            'missing-endpoint-attribution': lambda r: case(r)['stream_timing']['endpoint_forbid'].update(count=0),
            'missing-tx-replay': lambda r: r['tx'][0]['cases'].pop(),
            'missing-oracle-control': lambda r: r['negative_controls']['cases'].pop(),
            'stale-recovery': lambda r: r['recovery'].update(current_production_inputs_match=False),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                corrupt = copy.deepcopy(record)
                change(corrupt)
                with self.assertRaises(RuntimeError):
                    validate(corrupt)


if __name__ == '__main__':
    unittest.main()
