"""Context-specific emitted call-depth bound for the IDE resident worker.

IOCORE runs on its caller's stack. The IDE worker's only device binding is the
immutable timer request. Exclude impossible SIO/IDE startup and non-timer
resident dispatch branches; retain matching/name checks and every timer path.
Exec COP services use the separately reserved kernel stack. This is a focused
source/ABI proof, not a general compiler stack analysis.
"""
import json
from pathlib import Path
from native_program import read_build,require,sha256
from native_frame_maps import validate
from generate_sio_adapter import ABI


def direct_calls(body,targets):
    """Find known JSL targets without interpreting their address operands again."""
    calls=[];offset=0
    while offset+4<=len(body):
        target=int.from_bytes(body[offset+1:offset+4],'little')
        if body[offset]==0x22 and target in targets:
            calls.append(target);offset+=4
        else:offset+=1
    return calls


def record(output):
    p=read_build(output);image=p['image'];validate(image['routines'])
    routines={r['address']:r for r in image['routines']}
    imports={r['address']:r for r in image['imports']}
    segments={s['address']:bytes(s['bytes']) for s in image['segments']}
    targets=routines.keys()|imports.keys()
    labels={int(line.split()[1],16):line.split()[2][1:] for line in (output/'hosted.lbl').read_text().splitlines() if not line.split()[2].endswith('_end')}
    native=(output/'hosted.bin.signals').read_bytes()
    origin=p['build']['task_storage']['BASE']+ABI['native_offset']
    memo={};pruned=[]

    def bound(address,path):
        if address in memo:return memo[address]
        require(address not in path,'Unbounded worker call cycle: '+str([labels.get(a,routines.get(a,{}).get('name',hex(a))) for a in path+[address]]))
        if address in imports:
            item=imports[address];result=(item['stack_peak'],[labels.get(address,hex(address))])
            body=native[address-origin:address-origin+item['size']] if origin<=address<origin+len(native) else b''
            # Checked caller thunks finish with JML into ordinary emitted code.
            if len(body)>=4 and body[-4]==0x5c:
                target=int.from_bytes(body[-3:],'little')
                if target in routines:
                    other=bound(target,path+[address])
                    if other[0]>result[0]:result=(other[0],[labels.get(address,hex(address))]+other[1])
            memo[address]=result;return result
        r=routines[address];body=segments[address]
        calls=direct_calls(body,targets)
        require(len(calls)==len(r['calls']),'Emitted direct call accounting changed: '+r['name'])
        result=(r['fixed_frame'],[r['name']])
        for target,call in zip(calls,r['calls']):
            name=routines.get(target,{}).get('name','')
            impossible=(r['name'].startswith(('M_IOCORE_OPENDEVICE_','M_IOADMISSION_START_')) and name.startswith(('M_SIODRIVER_START_','M_IDEPLUSDRIVER_START_')) or r['name'].startswith('M_IORESIDENT_') and name.startswith(('M_SIODRIVER_','M_IDEPLUSDRIVER_','M_CONSOLEDRIVER_')))
            if impossible:
                pruned.append([r['name'],name]);continue
            child=bound(target,path+[address])
            cost=r['fixed_frame']+call['outgoing']+call['transfer_peak']+child[0]
            if cost>result[0]:result=(cost,[r['name']]+child[1])
        memo[address]=result;return result
    worker=next(a for a,r in routines.items() if r['name'].startswith('M_IDEPLUSDRIVER_WORKER_'))
    ordinary,path=bound(worker,[])
    # Include the full interrupt reserve and a conservative dispatch-entry margin.
    total=ordinary+256+16
    require(total<=1024,'IDE worker does not fit the admitted 1 KiB stack')
    result=dict(status='pass',tier='development',image_sha256=sha256(output/'program.a816.json'),ordinary_call_bound=ordinary,interrupt_reserve=256,dispatch_margin=16,total_bound=total,reservation=1024,headroom=1024-total,deepest_path=path,unreachable_timer_binding_branches=pruned,visited_entries=len(memo),assumptions=['IDE worker opens only its immutable timer.device request','IORESIDENT callbacks on this worker therefore select timer.device','COP policy switches to the reserved kernel stack; interrupt frames use the 256-byte reserve','Emitted worker paths use direct calls; known targets match every compiler call-map entry'])
    (output/'ideplus-stack-bound.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import sys
    print(json.dumps(record(Path(sys.argv[1]).resolve()),indent=2))
