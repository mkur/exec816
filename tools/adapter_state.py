"""Resolve the hosted adapter state from the platform profile and ABI offsets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def addresses(profile=None):
    profile = profile or json.loads((ROOT/'platform/altirraos/memory-1m.json').read_text())
    region = next(r for r in profile['regions'] if r['name'] == 'state')
    offsets = json.loads((ROOT/'abi/exec816-v1.json').read_text())['state_offsets']
    if region['size'] != 256 or any(not 0 <= value < 256 for value in offsets.values()):
        raise ValueError('Invalid adapter state page')
    return dict(STATE=region['address'], STATE_BYTES=region['size'],
                **{name:region['address']+offset for name,offset in offsets.items()})


# Host observers use the same single supported placement as generated bindings.
globals().update(addresses())
STOPPED = f'dw(${STATUS:04x})!=$ffff'
