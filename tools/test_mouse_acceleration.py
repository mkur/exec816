#!/usr/bin/env python3
"""Run rational-model cases through emitted desktop pointer code."""
import argparse
import json
import os
import re
import struct
from pathlib import Path
from bitmap_console_performance import native_markers
from mouse_acceleration_oracle import cases
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from sio_transaction_trace import read_events,stats


def audit(program,out):
    decoder={'__name__':'mouse_decoder'}
    path=ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(),str(path),'exec'),decoder)
    image=program['image']
    routines=[r for r in image['routines'] if r['name'].startswith('M_DESKMOUSE_')]
    allowed={r['address'] for r in routines}
    calls=[];listings=[]
    for r in routines:
        segments=[]
        for s in image['segments']:
            lo=max(s['address'],r['address']);hi=min(s['address']+len(s['bytes']),r['address']+r['size'])
            if lo<hi:segments.append(dict(address=lo,executable=True,bytes=s['bytes'][lo-s['address']:hi-s['address']]))
        listing=decoder['disassemble']({**image,'version':3,'segments':segments})
        listings.append(r['name']+'\n'+listing)
        for target in re.findall(r' JSL \$([0-9A-F]{6})',listing):
            require(int(target,16) in allowed,'Unexpected runtime/helper call in mouse transform: '+target)
            calls.append(target)
        require(not re.search(r'\bJSR\b',listing),'Unexpected near helper in mouse transform')
    (out/'transform.lst').write_text('\n'.join(listings))
    return dict(external_helper_calls=0,local_calls=calls,code_bytes=sum(r['size'] for r in routines))


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    rows=cases()
    payload=struct.pack('<H',len(rows))+b''.join(struct.pack('<BBhhhhHHhh',*row) for row in rows)
    p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/desktop_mouse_curve.act',out/'program',
            tasks=True,task_capacity=8,optimize=True,image_data=[(0x2d0000,payload)],console=False)
    spans=native_markers(p,[('DESKMOUSE_APPLY','apply')])
    points=[spans['apply']['entry'],*spans['apply']['returns']]
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='0',EXEC816_LATENCY_PCS=','.join(f'{n:x}' for n in points))
    report=dict(status='running',tier='development',qualification=False,build=p['build'],cases=len(rows),
                oracle_sha256=sha256(ROOT/'tools/mouse_acceleration_oracle.py'))
    report['arithmetic_audit']=audit(p,out)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            b.profile_start()
            try:
                report['runtime'],_=execute(b,p,timeout=100,frame_limit=5000)
            finally:
                report['checks']=data(b,p['image'],'checks',True)[0]
                report['index']=data(b,p['image'],'index',True)[0]
                report['event']=bytes(data(b,p['image'],'event')).hex()
            b.profile_stop()
            require(report['checks']==len(rows),'Incomplete curve fixture')
            clean_ownership(b,p,p['output'])
        pending=None;costs=[]
        for cycle,event in read_events(out/'emulator.log'):
            if event[0]!='cpu':continue
            pc=int(event[4],16)
            if pc==points[0]:pending=cycle
            elif pc in points[1:] and pending is not None:
                costs.append(cycle-pending);pending=None
        require(len(costs)==len(rows),'Missing pointer transform timing spans')
        report['apply_wall_time']=stats(costs)
        report['status']='pass'
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Mouse transform passed',len(rows),'cases',report['apply_wall_time'],flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
