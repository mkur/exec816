#!/usr/bin/env python3
"""Isolated emitted CPU costs; no desktop or physical latency qualification."""
import argparse,json,os,subprocess
from pathlib import Path
from unittest.mock import patch
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from measure_fastbasic_responsive import fixture_source,distribution
from sio_transaction_trace import read_events,BASE_HZ


def run(out,observer,revision=None):
    out.mkdir(parents=True,exist_ok=True)
    origin=ROOT/'examples/gem-basic'
    if revision:
        origin=out/'sources';origin.mkdir(exist_ok=True)
        for name in ('assist.c','assist.h','assist-ui.c','assist-ui.h','editor.h','editor-paint.c','document.c','document.h'):
            raw=subprocess.check_output(['git','show',revision+':examples/gem-basic/'+name],cwd=ROOT)
            (origin/name).write_bytes(raw)
    raw=fixture_source();header=out/'component-source.h' 
    header.write_text('static const UBYTE componentSource[]={'+','.join(map(str,raw))+'};\n')
    source=(origin/'document.c').read_text()
    source=source.replace('static void apply(', 'extern void ComponentMoveBegin(void),ComponentMoveEnd(void),ComponentIndexBegin(void),ComponentIndexEnd(void);\nstatic void apply(',1)
    require(source.count('move_gap(d,at);')==1,'Gap attribution hook changed')
    source=source.replace('move_gap(d,at);','ComponentMoveBegin();move_gap(d,at);ComponentMoveEnd();',1)
    needle='    /* Maintain source-line offsets' if '/* Maintain source-line offsets' in source else '    memmove(d->line+'
    require(source.count(needle)==1,'Index attribution hook changed')
    source=source.replace(needle,'    ComponentIndexBegin();\n'+needle,1)
    end=source.index('\n}\n\nWORD BasicReplace(',source.index('static void apply('))
    source=source[:end]+'\n    ComponentIndexEnd();'+source[end:]
    doc=out/'document-profile.c';doc.write_text(source)
    markers=('Color','Far','Tiny','Move','Index');names=[f'Component{k}{edge}' for k in markers for edge in ('Begin','End')]
    mark=out/'markers.c';mark.write_text('#include <exec/types.h>\nvolatile UWORD ComponentPhase;\n'+''.join(f'void {n}(void){{ComponentPhase={i+1};}}\n' for i,n in enumerate(names)))
    compose='BasicAssistanceCompose' in (origin/'assist-ui.h').read_text()
    row=''
    if not compose:
        painter=(origin/'editor-paint.c').read_text()
        row=painter[painter.index('static void row_text('):painter.index('static void compose(')].replace('row_text','ComponentRowText')
    (out/'component-row.h').write_text(row)
    sources=[ROOT/'tests/programs/basic_components.c',doc,mark,origin/'assist.c',origin/'assist-ui.c',ROOT/'c/calypsi/exec.c']
    f=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),True,
        roots=['ComponentProbe','ComponentChecks',*names],includes=[out,origin,ROOT/'examples/gem-basic'],
        definitions={'markers.c':['--no-interprocedural-cross-jump'],
            'assist-ui.c':['--no-interprocedural-cross-jump'],
            'basic_components.c':['-DCOMPONENT_COMPOSE=1'] if compose else []})
    fixture=out/'probe.act';fixture.write_text('MODULE COMPONENTPROBE\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
        '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%f['symbols']['ComponentProbe'])
    p=build(compiler(ROOT/'build/actionc',release=True),fixture,out/'program',tasks=True,
        task_capacity=8,foreign_image=f,optimize=True,console=False,stack_checks=True)
    pcs=','.join(f'{f["symbols"][n]:x}' for n in names)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(Path(observer['binary']))==observer['sha256'],'Changed passive observer')
    with patch.dict(os.environ,EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=pcs,EXEC816_EDITOR_HISTORY='1'):
        with emulator(Path(observer['binary']).parent,rom,out,pin=pin) as b:
            machine=verify_machine(b,rom,pin)
            runtime,_=execute(b,p,timeout=180,frame_limit=9000,timer_irq=True,
                before_run=lambda b:b._cmd_ok('KEY ALL up'))
            require(data(b,p['image'],'result',True)==[0,0],'Component fixture failed')
            ownership(b,p,p['output']);checks=b.peek16(f['symbols']['ComponentChecks'])
    events=read_events(out/'emulator.log',kinds={'cpu'});active={};costs={k:[] for k in markers}
    for tick,e in events:
        pc=int(e[4],16)
        for k in markers:
            if pc==f['symbols']['Component'+k+'Begin']:
                require(k not in active,'Nested '+k);active[k]=tick
            elif pc==f['symbols']['Component'+k+'End']:
                require(k in active,'Missing '+k+' entry');costs[k].append((tick-active.pop(k))*1000/BASE_HZ)
    require(not active and all(len(v)==(40 if k in ('Move','Index') else 20) for k,v in costs.items()),'Incomplete attribution samples')
    record=dict(status='pass',tier='development',qualification=False,checks=checks,
        scope='Isolated native CPU intervals, 32KiB gap and 19x56 comment-row composition, includes marker overhead/interrupts; excludes desktop peer contention and real graphics',
        machine=machine,runtime=runtime,observer=observer,compose=compose,
        milliseconds={k:distribution(v) for k,v in costs.items()},
        samples_ms=costs,document_sha256=sha256(origin/'document.c'),source_revision=revision,source_row_sha256=sha256(out/'component-row.h'),
        instrumented_document_sha256=sha256(doc),sources={str(q):sha256(q) for q in sources},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--observer-pin',type=Path,required=True);a.add_argument('--source-revision');v=a.parse_args()
    print(run(v.output.resolve(),json.loads(v.observer_pin.read_text()),v.source_revision)['status'])
