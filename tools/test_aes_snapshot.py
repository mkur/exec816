#!/usr/bin/env python3
"""Controlled emitted UPDATE metadata cost and freshness checks."""
import argparse
import json
import os
import struct
from pathlib import Path
from unittest.mock import patch
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import native_calls
from measure_magic_aes import summary
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from sio_transaction_trace import read_events
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def check_observations(raw):
    from generate_desktop import ABI
    c=ABI['constants'];rows=[]
    for offset in range(0,len(raw),320):
        u=struct.unpack_from('<160H',raw,offset)
        s=struct.unpack_from('<160h',raw,offset)
        count,icon,kind,shown=u[:4]
        bounds=[tuple(s[76+i*4:80+i*4]) for i in range(7)]
        source=tuple(s[118:122]) if icon else bounds[0]
        l,t,r,b=source
        work=source if kind&c['FRAME_BORDERLESS'] else (
            l+c['WORK_LEFT'],t+c['WORK_TOP']+(c['FRAME_INFO_HEIGHT'] if kind&c['FRAME_INFO'] else 0)
            +(c['FRAME_TAB_HEIGHT'] if kind&c['FRAME_SHELL_TABS'] else 0),
            r-(c['FRAME_GADGET_WIDTH'] if kind&c['FRAME_VERTICAL'] else c['WORK_RIGHT']),
            b-(c['FRAME_GADGET_HEIGHT'] if kind&c['FRAME_SIZER'] else c['WORK_BOTTOM']))
        require(tuple(s[4:8])==source and tuple(s[8:12])==work,'Snapshot work/bounds differs')
        require(shown==(0 if icon else u[104]),'Snapshot shown differs')
        cells=lambda q:{(x,y) for y in range(q[1],q[3]) for x in range(q[0],q[2])}
        want=set() if icon or not shown else cells(work)&cells(bounds[0])
        order=u[111:118]
        for slot in order[:order.index(0)]:
            if u[104+slot]:want-=cells(bounds[slot])
        actual=set()
        require(count<=16,'Unbounded observed visibility')
        rects=[]
        for i in range(count):
            rect=tuple(s[12+i*4:16+i*4]);part=cells(rect)
            require(not actual&part,'Overlapping visible rectangles')
            actual|=part;rects.append(rect)
        require(actual==want,'Snapshot visibility differs at observation '+str(len(rows)))
        rows.append(dict(bounds=source,work=work,shown=shown,rectangles=rects,
            revision=u[122]+(u[123]<<16),paint_epoch=u[124]+(u[125]<<16),pixels_ready=u[126]))
    require(len(rows)==22,'Incomplete freshness corpus: '+str(len(rows)))
    return rows


def run(out,from_build=None,epochs=False):
    out.mkdir(parents=True,exist_ok=True)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=16384
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    source=ROOT/'tests/programs/aes_snapshot.act'
    if epochs:
        from library_paths import read_source
        (out/'snapshotfaults.act').write_text('MODULE SNAPSHOTFAULTS\nPUBLIC BYTE fail\nENDMODULE\n')
        layers=read_source(ROOT/'lib/display/layers.act').replace('USE LAYERTYPES','USE LAYERTYPES\nUSE SNAPSHOTFAULTS',1)
        needle='          status=REGIONS.Subtract(@layer.visible,@above.bounds,@scene.work)'
        require(layers.count(needle)==1,'Visibility fault boundary changed')
        layers=layers.replace(needle,needle+'\n          IF SNAPSHOTFAULTS.fail<>0 THEN\n            status=LAYERTYPES.FULL\n          FI')
        (out/'layers.act').write_text(layers)
        fixture=read_source(source).replace('USE REGIONS','USE REGIONS\nUSE SNAPSHOTFAULTS',1)
        fixture=fixture.replace('PUBLIC PROC Sample()',
            'INCLUDE "'+str(ROOT/'tests/programs/aes-snapshot-epoch-checks.inc')+'"\n\nPUBLIC PROC Sample()',1)
        fixture=fixture.replace('  FreshnessChecks()\n','  FreshnessChecks()\n  EpochChecks()\n',1)
        source=out/'probe.act';source.write_text(fixture)
    p=read_build(from_build/'program') if from_build else build(
        compiler(ROOT/'build/actionc',release=True),source,
        out/'program',tasks=True,task_capacity=8,optimize=True,console=False,console_deferred=True,
        memory_profile=memory)
    names='AESSNAPSHOTPROBE_SAMPLE AESWINDOWSTATE_BEGINUPDATE AESWINDOWSTATE_SNAPSHOTALL AESWINDOWSTATE_PUBLISH AESWINDOWSTATE_ENDUPDATE REGIONS_CLIP'.split()
    if epochs:names+=['AESSNAPSHOTPROBE_ZEROEPOCHSAMPLES']
    marks=native_markers(p,[(n,n) for n in names])
    require(set(marks)==set(names),'Missing metadata marker')
    points={n:p['labels'][n] for n in ('native_irq','native_nmi','interrupt_schedule')}
    points.update(selected=p['labels']['context_restore']+4,turn=marks[names[0]]['entry'])
    definition=dict(points=points,spans={},task_dps=[t['dp'] for t in p['build']['memory']['task_pools']])
    pcs=set(points.values())|{pc for m in marks.values() for pc in [m['entry'],*m['returns']]}
    environment=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)),EXEC816_MASK_TRACE='0')
    report=dict(status='running',tier='development',qualification=False,build=p['build'],
        harness_sha256=sha256(Path(__file__)),fixture_sha256=sha256(source),epochs=epochs)
    try:
        with patch.dict(os.environ,environment),emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            try:report['runtime'],_=execute(b,p,before_run=lambda b:b.profile_start(),timeout=120,frame_limit=6000)
            finally:b.profile_stop()
            ownership(b,p,p['output'])
            report['checks']=data(b,p['image'],'checks',True)[0]
            observed=next(d['address'] for d in p['image']['data'] if '_AESSNAPSHOTPROBE_OBSERVATIONS_' in d['name'])
            count=data(b,p['image'],'observationCount',True)[0]
            report['observations']=check_observations(b.memdump(observed,count*320))
        events=read_events(out/'emulator.log',kinds={'cpu'})
        profile=analyze_events(events,definition,include_segments=True)
        spans=native_calls(events,marks)
        if epochs:
            zero=[s for s in spans if s['kind']=='AESSNAPSHOTPROBE_ZEROEPOCHSAMPLES']
            require(len(zero)==1,'Missing zero-epoch probe')
            clips=[s for s in spans if s['kind']=='REGIONS_CLIP' and
                   zero[0]['start']<=s['start']<s['end']<=zero[0]['end']]
            require(len(clips)==8,'Exhausted epoch must reconstruct every view')
            report['zero_epoch_clip_calls']=len(clips)
        clock=Timeline(profile['segments'],profile['worker_dp'])
        samples=sorted((s for s in spans if s['kind']==names[0]),key=lambda s:s['start'])
        require(len(samples)==40,'Wrong controlled workload count')
        groups={}
        for i,name in enumerate(('one_fixed','four_fixed','four_fragmented','four_changed')):
            selected=samples[i*10+2:i*10+10]
            helpers={}
            for n in names[1:]:
                rows=[[s for s in spans if s['kind']==n and w['start']<=s['start']<s['end']<=w['end']] for w in selected]
                helpers[n]=dict(calls=summary([len(r) for r in rows]),
                    caller_cpu_ms=summary([sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in r) for r in rows]))
            groups[name]=dict(caller_cpu_ms=summary([clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in selected]),helpers=helpers)
        report.update(status='pass',groups=groups,marks=marks,definition=definition)
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Snapshot metadata checks passed:',report['checks'],flush=True)
    for name,g in groups.items():print(name,round(g['caller_cpu_ms']['median'],3),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    parser.add_argument('--epochs',action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.from_build.resolve() if args.from_build else None,args.epochs)
