#!/usr/bin/env python3
"""Interactive resident GEM applications; shared body for tests and demo."""
import argparse
import json
from pathlib import Path
from build_bitmap_console import drawing, prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT, build, compiler


def input_image(out, instrument=False):
    """The same resident bodies/wrapper are linked by proof and optional demo."""
    body=ROOT/'examples/gem-input/input.c'
    sources=[ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
             ROOT/'examples/gem-input/resident.c']
    if instrument:
        text=body.read_text().replace('#include "input.h"',
            '#include "'+str(ROOT/'examples/gem-input/input.h')+'"\n'
            'extern void InputBeforeWait(struct InputApp *);\nextern void InputObserved(struct InputApp *,WORD);\n'
            'extern void InputUpdateBegin(void),InputUpdateOwned(void),InputPaintDone(void),InputUpdateEnd(void);')
        text=text.replace('        events=evnt_multi', '        InputBeforeWait(app);\n        events=evnt_multi')
        text=text.replace('        if (!events)', '        InputObserved(app,events);\n        if (!events)')
        text=text.replace('    if (!wind_update(BEG_UPDATE)) return 0;',
            '    InputUpdateBegin();\n    if (!wind_update(BEG_UPDATE)) return 0;\n    InputUpdateOwned();')
        text=text.replace('    if (!wind_update(END_UPDATE)) okay=0;',
            '    InputPaintDone();\n    if (!wind_update(END_UPDATE)) okay=0;\n    InputUpdateEnd();')
        body=out/'input.c';body.write_text(text)
        sources.append(ROOT/'tests/programs/gem_input_probe.c')
        events=ROOT/'c/calypsi/aes-events.c'
        text=events.read_text().replace('#include "aes-private.h"',
            '#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\nextern void InputEventWait(struct ExecAESContext *);')
        text=text.replace('        Wait(mask);','        InputEventWait(c);\n        Wait(mask);')
        altered=out/'aes-events.c';altered.write_text(text)
        sources[sources.index(events)]=altered
    sources.append(body)
    return drawing(out,True,widgets=True,client_sources=sources,
        client_entries=['GEMInputOne','GEMInputTwo']+(['InputHold'] if instrument else []),
        client_roots=['GEMInputsStart','GEMInputsStop','GEMInputsService','GEMInputs']+(['InputPost','InputCapacity'] if instrument else []),
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_input_layout.c',[
                ('Input size',212),('Input ready',12),('Input activations',14),
                ('Input paints',18),('Input message',22),('Input work',38),('Input key',46),('Input clicks',56),
                ('Input down',70),('Input armed',72),('Input tick',74)])])


def input_bindings(source,foreign):
    sy=foreign['symbols']
    # Append library-like native stubs before Main. No application policy lives
    # here: startup supplies the endpoint and the C wrapper owns Task lifetime.
    stub=f"""CARD FUNC POINTER inputCall()

BYTE FUNC InputsStart()

  LET endpoint=LONGCARD POINTER(${sy['GEMInputsService']:x})
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET entry=ADDRESS POINTER(@inputCall)
  entry^=${sy['GEMInputsStart']:x}

RETURN(inputCall()<>0)

BYTE FUNC InputsStop()

  LET entry=ADDRESS POINTER(@inputCall)
  entry^=${sy['GEMInputsStop']:x}

RETURN(inputCall()<>0)

"""
    if 'InputPost' in sy:
        for name in ('InputPost','InputCapacity'):
            stub+=f'BYTE FUNC {name}()\n\n  LET endpoint=LONGCARD POINTER(${sy["GEMInputsService"]:x})\n  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))\n  LET entry=ADDRESS POINTER(@inputCall)\n  entry^=${sy[name]:x}\n\nRETURN(inputCall()<>0)\n\n'
    return source.replace('PROC Main()',stub+'PROC Main()',1)


def build_inputs(out,source=None,program_output=None,load=False,panel=False,**options):
    from library_paths import read_source
    out.mkdir(parents=True,exist_ok=True)
    instrument=source is None and not load
    options.pop('desktop',None)
    foreign=input_image(out,instrument)
    original=source or ROOT/('tests/programs/gem_input_load.act' if load else 'tests/programs/gem_input_session.act')
    text=read_source(original)
    if panel:text=text.replace('CONST WITH_PANEL=0','CONST WITH_PANEL=1')
    source=out/'inputs.act';source.write_text(input_bindings(text,foreign))
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--load',action='store_true')
    parser.add_argument('--panel',action='store_true',help='Separate four-layer native-panel coexistence fixture; implies --load')
    parser.add_argument('--mouse-profile',choices=('off','mild'))
    args=parser.parse_args()
    build_inputs(args.output.resolve(),mouse_profile=args.mouse_profile,stack_checks=True,load=args.load or args.panel,panel=args.panel,
        **(dict(dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2)]) if args.load or args.panel else {}))
