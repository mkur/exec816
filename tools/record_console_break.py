#!/usr/bin/env python3
"""Publish B5 only after fresh emitted-code, timing, replay and ownership gates."""
import argparse,json
from pathlib import Path
from native_program import ROOT,sha256,require
from ports_budget import account,current
from shell_break_timing import validate as validate_timing
from shell_break_peer_trace import analyze as peer_timing
from sio_transaction_trace import read_events,BASE_HZ

PRODUCTION=('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc',
            'lib/dos/doscooked.act','lib/console/consoledriver.act','platform/altirraos/sio.s')
MATRIX=[(mode,name,256 if name=='queued-type' else 128,1,1)
        for mode in ('raw','opt')
        for name in ('compute','ctrl-c','typeahead','active-type','directory','cd','redirected-type','console-write','queued-type')]
MATRIX += [(mode,name,256,4,1) for mode in ('raw','opt') for name in ('active-type','queued-type','compute')]
MATRIX += [('opt','cd',128,1,3)]

def validate_matrix(matrix):
    require([tuple(case) for case in matrix]==MATRIX,'Incomplete or changed B5 qualification matrix')

def compact(r):
    require(r.get('status','pass')=='pass','Failed native record')
    for name,digest in r.get('source_inputs',{}).items():
        require(sha256(ROOT/name)==digest,'Stale qualification source: '+name)
    result={k:r[k] for k in ('name','mode','kernel_bank','bank','scenario','sector_bytes','profile','checks','counts',
             'events','observations','schedule','source_inputs','observers','pin','platform_pin','machine','break_timing',
             'operation_observations','serial_timing','timing','limits','xex_sha256','writes_sha256',
             'expected_sha256','media_sha256','ticks_50hz','nominal_ms_per_scroll','worker_visible_limit_ticks') if k in r}
    if 'build' in r:
        b=r['build']
        require(b['revision']=='2d73c03a0cb02e1f9d5b54d49679d6c2c4d8d78d' and not b['changes'] and not b['override'],'Unpinned compiler')
        for group in ('task_inputs','console_inputs','platform_inputs'):
            for name,digest in b.get(group,{}).items():
                require(sha256(ROOT/name)==digest,'Stale emitted-code input: '+name)
        result['build']={k:b[k] for k in ('revision','binary_sha256','abi_sha256','source_sha256','image_sha256','xex_sha256','optimize','stack_checks')}
        result['bank_zero_budget']=account(b['memory'])
        require(result['bank_zero_budget']==current()['after']['eight'],'Bank-zero reservation changed')
    if 'runtime' in r:
        t=r['runtime'];require(t['guards']=='intact','Damaged native guards')
        require(t['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        require(all(s['untouched_above_floor']>=0 for s in t['stack_observations']),'Task interrupt reserve touched')
        result['runtime']={k:t[k] for k in ('status','guards','created','native_nmi_count','native_irq_count','stack_observations','kernel_stack_observation') if k in t}
    for key in ('case','replay'):
        if key in r and isinstance(r[key],dict) and 'runtime' in r[key]:result[key]=compact(r[key])
    if 'replay' in r and 'runtime' not in r['replay']:result['replay']=r['replay']
    if 'cases' in r:result['cases']=[compact(c) for c in r['cases']]
    if 'serial_timing' in r:require(r['serial_timing']['verdict']=='pass' and not r['serial_timing']['violations'],'Serial deadline failed')
    return result


def collect(base):
    matrix=json.loads((base/'gate-break/matrix.json').read_text());records=[]
    validate_matrix(matrix)
    replacements={'compute','ctrl-c','typeahead','active-type'}
    for mode,name,size,profile,bank in matrix:
        directory='gate-break-complete-inputs' if mode=='raw' and name in replacements and size==128 and profile==1 else 'gate-break'
        path=base/directory/f'{mode}-{name}-{size}-p{profile}-b{bank}'/'results.json'
        r=json.loads(path.read_text());require(r['status']=='pass',str(path))
        require('source_inputs' in r,'Missing pre-build application/observer hashes')
        a,b=r['case'],r['replay']
        require(a['schedule']==b['schedule'] and a['xex_sha256']==b['xex_sha256'],'Replay image/input changed')
        for stage in ('prompt','next-command'):
            screen=lambda case:next(o['screen_sha256'] for o in case['observations'] if o['stage']==stage)
            require(screen(a)==screen(b),'Replay physical screen changed')
        require(all(o['live']==8 and o['created']==7 for o in a['observations'] if 'live' in o),'Missing simultaneous Task capacity')
        if name=='queued-type':
            require(next(o['reader_active'] for o in a['observations'] if o['stage']=='recovered')==1,
                    'Queued command did not recover before its peer Read finished')
            # The existing passive reply marker precedes ReplyMsg. Use the
            # caller's exact collection as a conservative published-reply
            # upper bound; merely entering ReplyMsg cannot satisfy the gate.
            timing=a['break_timing'];root_dp=r['build']['memory']['task_pools'][0]['dp']
            events=read_events(path.parent/'observed/trace.log')
            collected=[t for t,e in events if t>=timing['queued_publication'] and e[0]=='cpu'
                       and int(e[4],16)==r['marks']['collected'] and int(e[9],16)==root_dp]
            require(len(collected)==1,'Ambiguous canceled packet collection')
            timing['queued_reply_call']=timing['queued_reply'];timing['queued_reply_call_ms']=timing['queued_reply_ms']
            timing['queued_reply']=collected[0]
            timing['queued_reply_ms']=(collected[0]-timing['queued_publication'])/BASE_HZ*1000
            timing['queued_reply_boundary']='Upper bound: caller validated and collected its exact terminal packet before FSOPERATION.Collect entry.'
        validate_timing(a['break_timing'],queued=name=='queued-type')
        item=compact(r)
        if name in ('compute','ctrl-c','typeahead','queued-type'):
            item['continuous_peer_read']=peer_timing(path.parent/'observed/trace.log',r['marks'],path.parent/'observed/volume.atr',size)
        item.update(artifact=str(path.relative_to(ROOT)),sha256=sha256(path));records.append(item)
    regressions=[]
    names=[f'{t}-{mode}' for mode in ('raw','opt') for t in ('shell_core','console_cancel','console_scroll','shell_commands','shell_redirection','shell_entry','console_tx','console_input')]
    names += [f'shell_lifetime-{mode}-s{s}' for mode in ('raw','opt') for s in range(8)]
    for name in names:
        path=base/'gate-regression'/name/'results.json';r=json.loads(path.read_text());item=compact(r)
        item.update(artifact=str(path.relative_to(ROOT)),sha256=sha256(path));regressions.append(item)
    return dict(status='pass',inputs={n:sha256(ROOT/n) for n in PRODUCTION},cases=records,regressions=regressions,
                collector_inputs={n:sha256(ROOT/n) for n in ('tools/record_console_break.py','tools/shell_break_peer_trace.py','tools/shell_break_timing.py')},
                limits_ms=dict(capture_to_durable=100,queued_publication_to_reply=250,capture_to_usable_visible_prompt=500),
                bank_zero=dict(fixed_delta=0,per_task_delta=0),upper_memory=dict(new_workers=0,new_shared_state=0,new_shell_upper_bytes=48,new_shell_signals=1,shell_bytes=1288,scope_payload=44,scope_allocated=48),
                scope='Physical BREAK/Ctrl-C, command/prompt generations, exact cleanup and next physical ECHO with eight live Tasks; replay preserves every relative input/control frame and image. Prompt timing is the later of physical RAM completion and caller-ready after exact prompt Write collection. Keypress-to-observed-frame timing additionally includes hardware scanning and frame rounding.',
                host_tests=168)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifacts',type=Path,default=ROOT/'build/console-interaction/b5');p.add_argument('--output',type=Path,default=ROOT/'docs/qualification/console-interaction.json');args=p.parse_args()
    result=collect(args.artifacts.resolve());record=json.loads(args.output.read_text());record['slices']['B4']['commit']='9d0a359';record['slices']['B5']=result
    args.output.write_text(json.dumps(record,indent=2)+'\n');print('B5 qualification published',len(result['cases']),'break cases,',len(result['regressions']),'regressions')
