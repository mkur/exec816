"""Reserved memory delta against the frozen desktop DT0 image."""
import hashlib
import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[1]/'docs/development/desktop-dt0.json'


def delta(memory):
    data = BASELINE.read_bytes()
    before = json.loads(data)['bank_zero_budget']
    after = memory['bank_zero_budget']
    return dict(baseline='desktop-dt0', baseline_sha256=hashlib.sha256(data).hexdigest(),
                fixed=after['fixed_runtime']-before['fixed_runtime'],
                per_public_task=[a-b for a,b in zip(after['public'], before['public'])],
                idle=after['idle']-before['idle'],
                runtime=after['runtime_including_os']-before['runtime_including_os'],
                loading=after['loading_including_os']-before['loading_including_os'])
