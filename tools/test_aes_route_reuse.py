#!/usr/bin/env python3
"""Controlled optimized UPDATE/input-routing behavior and publication cost."""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from bitmap_console_performance import native_markers
from console_turn_profile import Timeline
from dos_concurrent_trace import call_marker
from g4bench_trace import native_calls
from measure_magic_aes import summary
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from sio_transaction_trace import read_events
from test_cooperative import data
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from text_performance_trace import timeline


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    from generate_memory import PROFILE
    memory=json.loads(PROFILE.read_text());memory['image_data_bytes']=16384
    profile=out/'fixture-memory.json';profile.write_text(json.dumps(memory,indent=2)+'\n')
    source=ROOT/'tests/programs/aes_route_reuse.act'
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',
        tasks=True,task_capacity=8,optimize=True,console=False,
        console_deferred=True,memory_profile=profile)
    names=('AESROUTEPROBE_SAMPLE','AESSNAPSHOT_PUBLISH','DESKGEOMETRY_WORK',
        'AESMOUSE_REFRESHSNAPSHOT','AESLOCKS_ACQUIRE','AESLOCKS_RELEASE',
        'AESROUTEPROBE_SWEEP','AESSNAPSHOT_DEFAULT')
    marks=native_markers(p,[(n,n) for n in names])
    require(set(marks)==set(names),'Missing route observer boundary')
    copy=call_marker(p,'M_AESSNAPSHOT_DEFAULT_','a816_memory_move')
    marks['default_copy']=dict(entry=copy,returns=[copy+4])
    points={n:p['labels'][n] for n in ('native_irq','native_nmi','interrupt_schedule')}
    points['selected']=p['labels']['context_restore']+4
    pcs=set(points.values())|{pc for m in marks.values() for pc in [m['entry'],*m['returns']]}
    report=dict(status='running',tier='development',qualification=False,build=p['build'],
        source_sha256=sha256(source),routing_sha256=sha256(ROOT/'lib/aes/aessnapshot.act'),
        observer_sha256=sha256(Path(__file__)))
    environment=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)),
        EXEC816_MASK_TRACE='0')
    try:
        with patch.dict(os.environ,environment),emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            try:report['runtime'],_=execute(b,p,before_run=lambda b:b.profile_start(),timeout=120,frame_limit=6000)
            except BaseException:
                report['checks']=data(b,p['image'],'checks',True)[0]
                raise
            finally:b.profile_stop()
            ownership(b,p,p['output'])
            report['checks']=data(b,p['image'],'checks',True)[0]
            report['route_bytes']=data(b,p['image'],'routeBytes',True)[0]
        events=read_events(out/'emulator.log',kinds={'cpu'})
        while events and int(events[-1][1][4],16) in (points['native_irq'],points['native_nmi']):events.pop()
        spans=native_calls(events,marks)
        samples=sorted((s for s in spans if s['kind']==names[0]),key=lambda s:s['start'])
        require(len(samples)==20,'Incomplete UPDATE pair cohort')
        clock=Timeline(timeline(events,points),samples[0]['dp'])
        groups={}
        def lookup_cost(sample):
            inside=[s for s in spans if sample['start']<=s['start']<s['end']<=sample['end']]
            defaults=[s for s in inside if s['kind']=='AESSNAPSHOT_DEFAULT']
            copies=[s for s in inside if s['kind']=='default_copy']
            return dict(default_calls=len(defaults),default_hits=sum(s['return_a']!=0 for s in defaults),
                default_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in defaults),
                default_copies=len(copies),default_copy_bytes=len(copies)*report['route_bytes'],
                default_copy_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in copies))
        for index,name in enumerate(('focused_owner','other_owner')):
            selected=samples[index*10+2:index*10+10]
            rows=[]
            for sample in selected:
                nested=[s for s in spans if sample['start']<=s['start']<s['end']<=sample['end']]
                publishes=[s for s in nested if s['kind']=='AESSNAPSHOT_PUBLISH']
                rows.append(dict(**clock.measure(sample['start'],sample['end']),**lookup_cost(sample),
                    publications=len(publishes),rebuilds=sum(s['return_a']!=0 for s in publishes),
                    publication_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in publishes),
                    geometry_calls=sum(s['kind']=='DESKGEOMETRY_WORK' for s in nested),
                    inbox_refreshes=sum(s['kind']=='AESMOUSE_REFRESHSNAPSHOT' for s in nested),
                    inbox_refresh_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms']
                        for s in nested if s['kind']=='AESMOUSE_REFRESHSNAPSHOT')))
            groups[name]={k:summary([r[k] for r in rows]) for k in rows[0]}
            groups[name]['samples']=rows
        sweeps=sorted((s for s in spans if s['kind']=='AESROUTEPROBE_SWEEP'),key=lambda s:s['start'])
        require(len(sweeps)==40,'Incomplete default lookup cohort')
        lookups={}
        for index,population in enumerate((0,1,2,4)):
            rows=[dict(**clock.measure(s['start'],s['end']),**lookup_cost(s))
                for s in sweeps[index*10+2:index*10+10]]
            require(all(r['default_calls']==4 and r['default_hits']==population for r in rows),
                'Default lookup population mismatch')
            lookups[str(population)]={k:summary([r[k] for r in rows]) for k in rows[0]}
            lookups[str(population)]['samples']=rows
        report.update(status='pass',groups=groups,lookups=lookups,marks=marks,
            reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,each_public_task=0,idle=0))
    except BaseException as error:
        report.update(status='fail',error=type(error).__name__+': '+str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Routing checks passed:',report['checks'],flush=True)
    for n,g in groups.items():print(n,'CPU',g['charged_cpu_ms']['mean'],'rebuilds',g['rebuilds']['mean'],flush=True)
    for n,g in lookups.items():print('populated',n,'CPU',g['charged_cpu_ms']['mean'],'copies',g['default_copies']['mean'],flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
