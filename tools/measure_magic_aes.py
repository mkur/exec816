#!/usr/bin/env python3
"""Optimized AES algorithm baseline with passive timing and full-frame pixels.

This is a focused native fixture, not a demo or a hosted qualification matrix.
Production C/Action! routines are compiled unchanged. Only the workload and
host debugger checkpoint control are new. Samples include fixture assertions.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import statistics
import struct
import subprocess
import sys
from unittest.mock import patch

import adapter_state as adapter
from aes_exposure_oracle import check_exposure_rectangles
from bitmap_console_oracle import Terminal
from bitmap_console_performance import native_markers
from build_bitmap_console import drawing, prepare
from console_turn_profile import Timeline, analyze_events
from desktop_oracle import compose
from generate_aes_server import expected_layout
from generate_desktop import ABI as DESKTOP_ABI, layout as desktop_layout
from generate_layers import layout as layers_layout
from generate_memory import PROFILE
from g4bench_trace import calls, listing_returns, native_calls
from gem_render_oracle import DESKTOP_PALETTE, PENS, font_bytes
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sio_transaction_trace import read_events
from test_dos_stack import execute, ownership
from test_gem_interactive import pixels
from test_mouse_observe import BRIDGE, PIN, ROM

NAMES = ('objects_5', 'objects_33_siblings', 'objects_9_nested',
         'counter_uncovered', 'counter_fragmented', 'counter_tick_fragmented',
         'separated_exposure', 'move_pending_redraw', 'zero_timer')
COUNTS = (8, 8, 8, 8, 8, 8, 3, 8, 8)
WARMUPS = 2


def build_fixture(out):
    fixture = ROOT/'tests/programs/magic_aes_baseline.c'
    foreign = drawing(out, True, widgets=True, client_sources=[
        ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c',
        ROOT/'c/calypsi/aes-events.c', fixture],
        client_roots=['MagicRun', 'MagicService', 'MagicBaselineProbe'],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())])
    sy = foreign['symbols']
    source = out/'baseline.act'
    source.write_text(f'''MODULE MAGICBASELINE
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE HEAPCORE

CARD FUNC POINTER run()

PROC Main()

  LET endpoint=LONGCARD POINTER(${sy['MagicService']:x})
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET entry=ADDRESS POINTER(@run)
  entry^=${sy['MagicRun']:x}
  IF run()=0 THEN
    HEAPCORE.Abort($fcf0)
  FI

  LET service=AESSTATE.Get()
  IF service.count<>0 OR AESCORE.Idle(service)=0 THEN
    HEAPCORE.Abort($fcf1)
  FI

RETURN
ENDMODULE
''')
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    launcher = prepare(source, out, foreign, desktop=True, aes=True)
    program = build(compiler(ROOT/'build/actionc', release=True), launcher,
        out/'program', optimize=True, tasks=True, task_capacity=8,
        foreign_image=foreign, console_deferred=True, memory_profile=memory)
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse'] = metadata(None)
    (program['output']/'build.json').write_text(json.dumps(program['build'], indent=2)+'\n')
    return program, foreign


def trace_definition(p, foreign, out):
    native = native_markers(p, [(n, n) for n in (
        'CONSOLEDRIVER_COLLECT', 'DESKMOVE_START', 'LAYERS_BEGINMOVE',
        'AESGUI_POST', 'AESWINDOWSTATE_DAMAGE')])
    address = p['labels']['context_restore']
    hosted = (p['output']/'hosted.bin').read_bytes()
    require(hosted[address-adapter.RESIDENT_BASE:address-adapter.RESIDENT_BASE+8]
        == bytes.fromhex('c230ab2b7afa6840'), 'Unknown context restore')
    points = {n:p['labels'][n] for n in ('native_irq', 'native_nmi', 'interrupt_schedule')}
    points.update(selected=address+4, turn=native['CONSOLEDRIVER_COLLECT']['entry'],
                  done=p['labels']['done'])
    for name, span in native.items():
        points[name] = span['entry']
        for i, pc in enumerate(span['returns']): points[name+str(i)] = pc
    sy = foreign['symbols']
    names = ('MagicBaselineProbe', 'App_ob_offset', 'objc_draw', 'ExecAESDraw',
             'wind_update', 'v_bar', 'v_gtext', 'DisplayEnter', 'DisplayLeave',
             'GemDrawingBorrow', 'GemDrawingSolidBorrow', 'VbxeOwnerSubmit',
             'GemDrawingCopyStart', 'ExecAESSubmit', 'DoIO', 'vdi_call')
    require(all(n in sy for n in names), 'Missing C measurement boundary')
    return dict(timeline=dict(points=points, spans={},
        task_dps=[t['dp'] for t in p['build']['memory']['task_pools']]),
        entries={sy[n]:n for n in names},
        returns=listing_returns(foreign, p['output'].parent/'drawing'), native=native)


def summary(values):
    return dict(min=min(values), median=statistics.median(values),
        mean=statistics.mean(values), max=max(values))


def analyze(out):
    definition = json.loads((out/'trace-definition.json').read_text())
    events = read_events(out/'emulator.log', kinds={'cpu'})
    # A final debugger stop at an IRQ entry has not executed that instruction.
    interrupts = {definition['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in interrupts: events.pop()
    profile = analyze_events(events, definition['timeline'], include_segments=True)
    native = native_calls(events, definition['native'])
    entries = {int(k):v for k,v in definition['entries'].items()}
    rows = []
    for dp in definition['timeline']['task_dps']:
        spans, unfinished = calls(events, entries, set(definition['returns']), dp)
        require(not any(s['kind']=='MagicBaselineProbe' for s in unfinished),
                'Incomplete workload call')
        clock = Timeline(profile['segments'], dp)
        presenter = Timeline(profile['segments'], profile['worker_dp'])
        for span in spans:
            if span['kind']!='MagicBaselineProbe': continue
            require(span['return_a']==1, 'Workload operation failed')
            nested = [s for s in spans if span['start']<=s['start']<s['end']<=span['end']]
            rows.append(dict(kind=NAMES[span['argument']], dp=dp,
                start=span['start'], end=span['end'],
                **clock.measure(span['start'], span['end']),
                presenter_cpu_ms=presenter.measure(span['start'], span['end'])['charged_cpu_ms'],
                calls=dict(Counter(s['kind'] for s in nested if s is not span)),
                inclusive_cpu_ms={n:sum(clock.measure(s['start'],s['end'])['charged_cpu_ms']
                    for s in nested if s['kind']==n) for n in set(entries.values())},
                native_returns={n:[s['return_a'] for s in native if s['kind']==n
                    and span['start']<=s['start']<s['end']<=span['end']]
                    for n in definition['native']}))
    groups = {}
    for i, name in enumerate(NAMES):
        selected = sorted((r for r in rows if r['kind']==name), key=lambda r:r['start'])
        warm = 0 if i==6 else WARMUPS
        require(len(selected)==COUNTS[i]+warm, 'Wrong sample count: '+name)
        selected = selected[warm:]
        groups[name] = dict(count=len(selected), discarded_warmups=warm,
            **{k:summary([r[k] for r in selected]) for k in (
                'charged_cpu_ms','presenter_cpu_ms','elapsed_ms','off_cpu_ms','interrupt_ms')},
            calls_per_sample={n:summary([r['calls'].get(n,0) for r in selected])
                for n in sorted(set().union(*(r['calls'] for r in selected)))},
            inclusive_cpu_ms={n:summary([r['inclusive_cpu_ms'][n] for r in selected])
                for n in set(entries.values())})
    result = dict(groups=groups, samples=rows, accounting=profile['scope'])
    (out/'timings.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def run(out, from_build=None):
    out.mkdir(parents=True, exist_ok=True)
    if from_build:
        p = read_build(from_build/'program')
        foreign = json.loads((from_build/'c-image.json').read_text())
    else: p, foreign = build_fixture(out)
    require(p['build']['optimize'], 'Baseline must be optimized')
    definition = trace_definition(p, foreign, out)
    (out/'trace-definition.json').write_text(json.dumps(definition, indent=2)+'\n')
    sy = foreign['symbols']
    pcs = set(definition['timeline']['points'].values())|set(definition['entries'])|set(definition['returns'])
    environment = dict(EXEC816_LATENCY_TRACE='1',
        EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)), EXEC816_MASK_TRACE='0')
    report = dict(status='running', tier='development', qualification=False,
        git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        working_tree=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        scope=__doc__, checkpoints=[], exposure_bursts=[], pin=PIN, build=p['build'],
        source_inputs=foreign['provenance']['source_inputs'],
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,per_public_task=[0]*8,idle=0),
        observer_inputs={str(x.relative_to(ROOT)):sha256(x) for x in (
            Path(__file__), ROOT/'tools/g4bench_trace.py', ROOT/'tools/console_turn_profile.py',
            ROOT/'tools/aes_exposure_oracle.py',
            ROOT/'tools/desktop_oracle.py', ROOT/'tests/programs/magic_aes_baseline.c',
            ROOT/'examples/gem-counter/counter.c', ROOT/'examples/gem-counter/counter.h')})
    report['source_inputs']['examples/gem-counter/counter.c']=sha256(ROOT/'examples/gem-counter/counter.c')
    report['source_inputs']['examples/gem-counter/counter.h']=sha256(ROOT/'examples/gem-counter/counter.h')
    (out/'working-tree.patch').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=ROOT))
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    from test_desktop_presentation import rectangle
    font = font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
    try:
        with patch.dict(os.environ, environment), emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine'] = verify_machine(b,ROM,PIN)
            get=lambda address,n=2:int.from_bytes(b.memdump(address,n),'little')
            at=lambda mod,n:next(d['address'] for d in p['image']['data']
                if '_'+mod+'_'+n.upper()+'_' in d['name'])
            def reach(condition):
                b.bp_clear_all()
                b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    value=original()
                    if int(value['PC'].lstrip('$'),16)==p['labels']['done']:
                        raise RuntimeError('Guest stopped before checkpoint: status '+hex(get(adapter.STATE))+
                            ', fixture line '+str(get(sy['MagicFirstFailure'])))
                    return value
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
                require(get(sy['MagicFailures'])==0, 'Fixture assertion '+str(get(sy['MagicFirstFailure'])))
            def frames(n): reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def phase(n): reach('dw($%x)=%d'%(sy['MagicPhase'],n))
            def pending():
                service=get(at('DESKSTATE','service'),3)
                dt=desktop_layout(); lt=layers_layout(); sf=dt['Service']['fields']; wf=dt['Window']['fields']
                scene=service+sf['scene']
                for i in range(DESKTOP_ABI['constants']['WINDOWS']):
                    window=service+sf['windows']+i*dt['Window']['size']
                    title=b.memdump(window+wf['title'],65).split(b'\0')[0]
                    if title==b'MagiC baseline':
                        ident=get(window+wf['layer'],4);break
                else: raise ValueError('Missing baseline window')
                for i in range(len(p['build']['memory']['task_pools'])+1):
                    layer=scene+lt['Scene']['fields']['items']+i*lt['Layer']['size']
                    if get(layer+lt['Layer']['fields']['id'],4)==ident:break
                else: raise ValueError('Missing baseline layer')
                damage=layer+lt['Layer']['fields']['pending']
                count=get(damage+lt['Damage']['fields']['count'])
                require(count<=8,'Unbounded pending damage')
                visible=layer+lt['Layer']['fields']['visible']
                return dict(count=count,visible_count=get(visible+lt['Region']['fields']['count']),
                    rectangles=[list(struct.unpack('<4h',b.memdump(
                    damage+lt['Damage']['fields']['rects']+i*8,8))) for i in range(count)])
            def checkpoint(n):
                frames(80)
                directory=out/f'checkpoint-{n}';directory.mkdir(exist_ok=True)
                work=struct.unpack('<4h',b.memdump(sy['MagicCounter']+38,8))
                count=get(sy['MagicCounter']+14,4)
                object_pixels=None
                if n in (1,2,3):
                    total=get(sy['MagicObjectsCount'])
                    require(total=={1:5,2:33,3:9}[n], 'Wrong object corpus')
                    raw=b.memdump(sy['MagicObjects'],total*24)
                    tree=[a.Obj(*struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(total)]
                    device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
                    x,y,w,h=work;device.dev.fill_rect(x,y,x+w-1,y+h-1,3)
                    aes=a.AES(device,tree,{})
                    aes.gsx_start();aes.gsx_sclip(a.Rect(*work));aes.ob_draw(0,8)
                    object_pixels=[(value>>shift)&15 for value in device.dev.s.mem[:76800] for shift in (4,0)]
                def external(r,title,bounds):
                    left,top,right,bottom=bounds
                    d=DESKTOP_ABI['constants']
                    l,t,rr,bb=left+d['WORK_LEFT'],top+d['WORK_TOP'],right-d['WORK_RIGHT'],bottom-d['WORK_BOTTOM']
                    if title==b'Occluder':
                        rectangle(r,(l,t,rr,bb),7);return
                    require(title==b'MagiC baseline','Unexpected application')
                    require(tuple(work)==(l,t,rr-l,bb-t),'Work geometry differs from independent frame geometry')
                    rectangle(r,(l,t,rr,bb),3)
                    if object_pixels is not None:
                        for y in range(t,bb):r.pixels[y*640+l:y*640+rr]=bytes(object_pixels[y*640+l:y*640+rr])
                    else:
                        r.clip=(l,t,rr-1,bb-1);r.text=4
                        r.apply(8,(l+8,t+14),('Count: %06d'%count).encode())
                        r.clip=(0,0,639,239)
                expected=compose(b,p,font,Terminal(64,20),(320,120),external,menu_contexts=sy['contexts'])
                digest=pixels(b,directory,expected,palette=DESKTOP_PALETTE)
                row=dict(phase=n,work=list(work),count=count,sha256=digest,
                    pixel_count=640*240,pending=pending())
                if n in (5,6):
                    require(row['pending']['visible_count']>1,'Missing fragmented visibility')
                report['checkpoints'].append(row)
                print('Pixels pass:',n,flush=True)
            def before(_):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                b.profile_start()
                for n in range(1,7):
                    phase(n);checkpoint(n);b.poke16(sy['MagicGo'],n)
                for i in range(3):
                    phase(70+i);frames(100)
                    report['exposure_bursts'].append(dict(iteration=i,pending_before=pending()))
                    b.poke16(sy['MagicGo'],70+i)
                    phase(80+i);checkpoint(80+i)
                    count=get(sy['MagicExposureCount'])
                    rects=[list(struct.unpack('<4h',b.memdump(sy['MagicExposureRects']+j*8,8))) for j in range(count)]
                    check_exposure_rectangles(rects,struct.unpack('<4h',b.memdump(sy['MagicCounter']+38,8)))
                    report['exposure_bursts'][-1].update(delivered_rectangles=rects,
                        requested_pixel_area=sum(r[2]*r[3] for r in rects),
                        newly_exposed_pixels=3*32*48)
                    b.poke16(sy['MagicGo'],80+i)
                for n in (8,9):
                    phase(n);checkpoint(n);b.poke16(sy['MagicGo'],n)
                b.bp_clear_all()
            try:
                report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            finally:b.profile_stop()
            ownership(b,p,p['output'])
            report['assertions']=get(sy['MagicChecks'])
            require(get(sy['MagicFailures'])==0,'Fixture failed')
        report['timings']=analyze(out)
        report['hashes']={name:sha256(path) for name,path in (
            ('xex',p['xex']),('trace',out/'emulator.log'),('definition',out/'trace-definition.json'))}
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    for name,row in report['timings']['groups'].items():
        print(name, 'CPU median ms',round(row['charged_cpu_ms']['median'],3),
            'elapsed median ms',round(row['elapsed_ms']['median'],3),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path,help='Reuse a frozen image in another output directory')
    args=parser.parse_args();run(args.output.resolve(),args.from_build.resolve() if args.from_build else None)
