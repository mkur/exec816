#!/usr/bin/env python3
"""Two resident GEM clients beside the production panel and root DOS workload."""
import argparse
import json
from pathlib import Path
from build_widget_panel import fixture
from build_desktop_input import fixture as input_fixture
from build_bitmap_console import drawing, prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT, build, compiler


def build_proof(out, load=False, pointer=False, mouse_profile=None):
    out.mkdir(parents=True, exist_ok=True)
    source=input_fixture(out, True) if pointer else fixture(out)
    foreign=drawing(out, True, widgets=True,
        client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c', ROOT/'c/calypsi/aes-events.c', ROOT/'tests/programs/aes_desktop.c'],
        client_entries=['AESClientOne', 'AESClientTwo'],
        client_roots=['AESStart', 'AESPump', 'AESStop', 'AESService'],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())])
    sy=foreign['symbols']
    text=source.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE AESBOOT\nUSE AESSTATE\n',1)
    text=text.replace('BYTE holdEvents', 'CARD FUNC POINTER aesCall()\nBYTE holdEvents')
    text=text.replace('  ready=1', f'''  BEGIN
    LET endpoint=LONGCARD POINTER(${sy['AESService']:x})
    endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
    LET entry=ADDRESS POINTER(@aesCall)
    entry^=${sy['AESStart']:x}
    Require(aesCall()=0)
    Require(AESBOOT.StopAdmission()=0)
  END
  ready=1''',1)
    text=text.replace('  WHILE mode<>9 DO', f'''  WHILE mode<>9 DO
    BEGIN
      LET entry=ADDRESS POINTER(@aesCall)
      entry^=${sy['AESPump']:x}
      Require(aesCall()=0)
    END''',1)
    text=text.replace('  DESKAPP.Stop()', f'''  BEGIN
    LET entry=ADDRESS POINTER(@aesCall)
    entry^=${sy['AESStop']:x}
    Require(aesCall()=0)
  END
  DESKAPP.Stop()''',1)
    if load:
        text=text.replace('  ready=1', f"  BEGIN\n    LET command=CARD POINTER(${sy['AESCommand']:x})\n    command^=5\n    LET entry=ADDRESS POINTER(@aesCall)\n    entry^=${sy['AESPump']:x}\n    Require(aesCall()=0)\n  END\n  ready=1",1)
    source.write_text(text)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    launcher=prepare(source,out,foreign,desktop=True,aes=True,mouse_profile=mouse_profile)
    program=build(compiler(ROOT/'build/actionc'),launcher,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2)])
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse']=metadata(mouse_profile)
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


def counter_image(out, instrument=False):
    """The same resident bodies/wrapper are linked by proof and optional demo."""
    body=ROOT/'examples/gem-counter/counter.c'
    sources=[ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
             ROOT/'examples/gem-counter/resident.c']
    if instrument:
        text=body.read_text().replace('#include "counter.h"',
            '#include "'+str(ROOT/'examples/gem-counter/counter.h')+'"\n'
            'extern void CounterBeforeWait(struct Counter *);\nextern void CounterObserved(struct Counter *,WORD);\n'
            'extern void CounterUpdateBegin(void),CounterUpdateOwned(void),CounterPaintDone(void),CounterUpdateEnd(void);')
        text=text.replace('        events=evnt_multi', '        CounterBeforeWait(app);\n        events=evnt_multi')
        text=text.replace('        if (!events)', '        CounterObserved(app,events);\n        if (!events)')
        text=text.replace('    if (!wind_update(BEG_UPDATE)) return 0;',
            '    CounterUpdateBegin();\n    if (!wind_update(BEG_UPDATE)) return 0;\n    CounterUpdateOwned();')
        text=text.replace('    if (!wind_update(END_UPDATE)) okay=0;',
            '    CounterPaintDone();\n    if (!wind_update(END_UPDATE)) okay=0;\n    CounterUpdateEnd();')
        body=out/'counter.c';body.write_text(text)
        sources.append(ROOT/'tests/programs/gem_counter_probe.c')
        events=ROOT/'c/calypsi/aes-events.c'
        text=events.read_text().replace('#include "aes-private.h"',
            '#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\nextern void CounterEventWait(struct ExecAESContext *);')
        text=text.replace('        Wait(mask);','        CounterEventWait(c);\n        Wait(mask);')
        altered=out/'aes-events.c';altered.write_text(text)
        sources[sources.index(events)]=altered
    sources.append(body)
    return drawing(out,True,widgets=True,client_sources=sources,
        client_entries=['GEMCounterOne','GEMCounterTwo']+(['CounterHold'] if instrument else []),
        client_roots=['GEMCountersStart','GEMCountersStop','GEMCountersService','GEMCounters']+(['CounterPost','CounterCapacity'] if instrument else []),
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_counter_layout.c',[
                ('Counter size',196),('Counter ready',12),('Counter count',14),
                ('Counter paints',18),('Counter message',22),('Counter work',38),('Counter label',46)])])


def counter_bindings(source,foreign):
    sy=foreign['symbols']
    # Append library-like native stubs before Main. No application policy lives
    # here: startup supplies the endpoint and the C wrapper owns Task lifetime.
    stub=f"""CARD FUNC POINTER counterCall()

BYTE FUNC CountersStart()

  LET endpoint=LONGCARD POINTER(${sy['GEMCountersService']:x})
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET entry=ADDRESS POINTER(@counterCall)
  entry^=${sy['GEMCountersStart']:x}

RETURN(counterCall()<>0)

BYTE FUNC CountersStop()

  LET entry=ADDRESS POINTER(@counterCall)
  entry^=${sy['GEMCountersStop']:x}

RETURN(counterCall()<>0)

"""
    if 'CounterPost' in sy:
        for name in ('CounterPost','CounterCapacity'):
            stub+=f'BYTE FUNC {name}()\n\n  LET endpoint=LONGCARD POINTER(${sy["GEMCountersService"]:x})\n  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))\n  LET entry=ADDRESS POINTER(@counterCall)\n  entry^=${sy[name]:x}\n\nRETURN(counterCall()<>0)\n\n'
    return source.replace('PROC Main()',stub+'PROC Main()',1)


def build_counters(out,source=None,program_output=None,**options):
    from library_paths import read_source
    out.mkdir(parents=True,exist_ok=True)
    instrument=source is None
    foreign=counter_image(out,instrument)
    original=source or ROOT/'tests/programs/gem_counter_session.act'
    source=out/'counters.act';source.write_text(counter_bindings(read_source(original),foreign))
    memory=options.pop('memory_profile',None)
    if memory is None:
        profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
        memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    mouse_profile=options.pop('mouse_profile',None)
    compiler_dir=options.pop('compiler_dir',ROOT/'build/actionc')
    launcher=prepare(source,out,foreign,desktop=True,aes=True,mouse_profile=mouse_profile)
    program=build(compiler(compiler_dir),launcher,program_output or out/'program',
        tasks=True,task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,**options)
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse']=metadata(mouse_profile)
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--counters',action='store_true')
    p.add_argument('--load',action='store_true',help='Start continuous GEM exchange for matched native feedback observations')
    p.add_argument('--pointer',action='store_true',help='Use the AS0 raw-event window for matched pointer observation')
    p.add_argument('--mouse-profile',choices=('off','mild'))
    args=p.parse_args()
    if args.counters:build_counters(args.output.resolve(),mouse_profile=args.mouse_profile)
    else:build_proof(args.output.resolve(),args.load,args.pointer,args.mouse_profile)
