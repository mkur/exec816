#!/usr/bin/env python3
"""Emitted raw hit snapshots and scene/UPDATE-independent caller queries."""
import argparse
import json
from pathlib import Path
from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, verify_machine, read_build
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out,publication=False,from_build=None):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=16384
    memory=out/'fixture-memory.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    source=ROOT/'tests/programs/aes_find.act'
    if publication:
        from library_paths import read_source
        (out/'publicationprobe.act').write_text(read_source(ROOT/'tests/programs/publicationprobe.act'))
        snapshot=read_source(ROOT/'lib/aes/aessnapshot.act')
        snapshot=snapshot.replace('USE EXEC\n','USE EXEC\nUSE PUBLICATIONPROBE\n',1)
        needle='    prepared.focus=desktop.focus'
        require(snapshot.count(needle)==1,'Snapshot pin boundary changed')
        (out/'aessnapshot.act').write_text(snapshot.replace(needle,
            '    PUBLICATIONPROBE.Pause()\n'+needle,1))
        probe=read_source(source).replace('USE EXEC\n','USE EXEC\nUSE PUBLICATIONPROBE\n',1)
        probe=probe.replace('  managerTask.tc_Node.ln_Type=EXEC.NT_TASK',
            '  PUBLICATIONPROBE.Check(@endpoint,ADDRESS(@AESSNAPSHOT.Invalidate),ADDRESS(@AESSNAPSHOT.Publish))\n  managerTask.tc_Node.ln_Type=EXEC.NT_TASK',1)
        source=out/'probe.act';source.write_text(probe)
    program=read_build(from_build/'program') if from_build else build(compiler(ROOT/'build/actionc',release=True),
        source,out/'program',
        tasks=True,task_capacity=8,optimize=True,memory_profile=memory,
        console=False,console_deferred=True)
    with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        runtime,_=execute(bridge,program,frame_limit=600,timeout=60)
        ownership(bridge,program,program['output'])
        checks=data(bridge,program['image'],'AESFINDTEST_CHECKS',True)[0]
        require(checks==110,'Incomplete committed hit checks: '+str(checks))
        publication_checks=data(bridge,program['image'],'PUBLICATIONPROBE_CHECKS',True)[0] if publication else 0
        if publication:require(publication_checks==10,'Incomplete publication lifetime checks: '+str(publication_checks))
    report=dict(status='pass',tier='development',qualification=False,mode='opt',
        checks=checks,publication_checks=publication_checks,
        machine=machine,runtime=runtime,build=program['build'])
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Committed hit checks passed:',checks,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--publication',action='store_true')
    parser.add_argument('--from-build',type=Path)
    args=parser.parse_args();run(args.output,args.publication,args.from_build.resolve() if args.from_build else None)
