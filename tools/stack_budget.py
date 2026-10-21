"""Development stack measurements and costs against the compact-layout baseline."""
import hashlib
import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1]/'docs/development/bank-zero-compaction.json'


def current_task_memory():
    """Default twelve-Task platform contract, independent of a fixture build."""
    from generate_memory import layout
    from task_capacity import configure
    memory = layout(upper_table=True)
    configure(memory, 12)
    return memory


def bank_zero_delta(memory):
    """Include each pool's guards, DP and unused capacity, including overrides."""
    source = BASELINE.read_bytes()
    key = 'four' if memory['task_capacity']==4 else 'eight'
    before = json.loads(source)['bank_zero']['after'][key]
    after = memory['bank_zero_budget']
    return dict(baseline='bank-zero-compaction',
                baseline_sha256=hashlib.sha256(source).hexdigest(),
                fixed=after['fixed_runtime']-before['fixed_runtime'],
                per_public_task=[a-(before['public'][i] if i<len(before['public']) else 0)
                                 for i,a in enumerate(after['public'])],
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
