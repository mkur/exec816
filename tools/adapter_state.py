"""Resolve the hosted adapter state from the platform profile and ABI offsets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def direct_pages(profile=None):
    """Resolve the physical DP map independently of the native field ABI."""
    profile = profile or json.loads((ROOT/'platform/altirraos/memory-1m.json').read_text())
    dp = profile['direct_pages']
    if (dp['task_stride'] != 256 or any(type(dp[k]) is not int or
            not 0 <= dp[k] <= 0xff00 or dp[k] % 256 for k in ('kernel','task_base'))):
        raise ValueError('Invalid aligned direct-page layout')
    return dict(KERNEL_DP=dp['kernel'], TASK0_DP=dp['task_base'],
                TASK1_DP=dp['task_base']+dp['task_stride'])


def stack_addresses(profile=None):
    """Resolve fixed bootstrap stacks; per-Task sizes use the capacity map."""
    profile = profile or json.loads((ROOT/'platform/altirraos/memory-1m.json').read_text())
    regions = {r['name']:r for r in profile['regions']}
    result = {}
    for owner in ('task0','task1','kernel'):
        region = regions[owner+'-stack']
        base, size = region['address']+16, region['size']-32
        if base % 16 or size != 1536 or not 16 <= base < base+size+16 <= 65536:
            raise ValueError('Invalid bootstrap stack reservation')
        result.update({owner.upper()+'_STACK_'+key:value for key,value in
                       dict(BASE=base,FLOOR=base+256,TOP=base+size-2,CEILING=base+size-1).items()})
    return result


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
globals().update(direct_pages())
globals().update(stack_addresses())
STOPPED = f'dw(${STATUS:04x})!=$ffff'
