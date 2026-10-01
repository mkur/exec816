"""Development stack measurements and costs against the compact-layout baseline."""
import hashlib
import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1]/'docs/development/bank-zero-compaction.json'


def bank_zero_delta(memory):
    """Include each pool's guards, DP and unused capacity, including overrides."""
    source = BASELINE.read_bytes()
    key = {4: 'four', 8: 'eight'}[memory['task_capacity']]
    before = json.loads(source)['bank_zero']['after'][key]
    after = memory['bank_zero_budget']
    return dict(baseline='bank-zero-compaction',
                baseline_sha256=hashlib.sha256(source).hexdigest(),
                fixed=after['fixed_runtime']-before['fixed_runtime'],
                per_public_task=[a-b for a,b in zip(after['public'],before['public'])],
                idle=after['idle']-before['idle'],
                runtime=after['runtime_including_os']-before['runtime_including_os'],
                loading=after['loading_including_os']-before['loading_including_os'])


def stack_usage(bridge, memory):
    """Read boot-fill high-water marks; reuse contributes to the same peak."""
    pools = [(str(i), p['stack_base'], p['stack_bytes'])
             for i,p in enumerate(memory['task_pools'])]
    low,high = memory['regions']['kernel-stack']
    pools.append(('kernel',low+16,high-low-32))
    result = {}
    for name,base,size in pools:
        raw = bridge.memdump(base,size)
        first = next((i for i,b in enumerate(raw) if b != 0xa5),size)
        result[name] = dict(base=base,bytes=size,peak=size-first,
                            remaining_above_floor=first-256)
    return result
