#!/usr/bin/env python3
"""Build the two-large-Task keyboard scene and root disk supervisor."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract, PORT
from gem_vdi_inputs import local_inputs
from library_paths import read_source
from native_program import ROOT, build, compiler, sha256
from generate_gem_vdi import expected_layout as gem_layout
from generate_gem_interactive import expected_layout as ui_layout, files
from generate_input import expected_layout as input_layout
from make_data_disk import make
from generate_dos_mounts import validate_mounts
from filesystem_formats import SDFS

def build_interactive(output,optimize=True,instrument=True):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    for p,content in files().items():
        if p.read_text()!=content: raise RuntimeError('Stale '+str(p))
    extraction=extract(output/'selected'); src=output/'selected/src'
    service=PORT/'service'; adapter=PORT/'adapter'; ui=PORT/'interactive'
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',ROOT/'c/calypsi/input.c',
        ROOT/'platform/altirraos/vbxe.c',service/'gem-validation.c',service/'gem-service.c',service/'gem-client.c',
        src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',adapter/'gem-vbxe.c',ui/'ui.c']
    if instrument: sources.append(ROOT/'tests/programs/gem_interactive_probe.c')
    foreign=emit(output,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',ROOT/'c/calypsi/input.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s'],
        ['GemApplication','GemServiceWorker']+(['UiUnusedTask'] if instrument else []),optimize=optimize,includes=[src,service,adapter,ui],
        definitions={'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
                     'ui.c':['-DGEM_DIAGNOSTIC'] if instrument else []},
        probes=[(service/'gem-layout.c',gem_layout()),(ui/'ui-layout.c',ui_layout()),
                (ROOT/'c/calypsi/input-layout.c',input_layout())])
    paths=[*adapter.glob('*'),*service.glob('*'),*ui.glob('*'),*PORT.glob('hosted/*'),*PORT.glob('patches/*'),
        ROOT/'platform/altirraos/vbxe.c',ROOT/'platform/altirraos/vbxe-map.s',ROOT/'abi/console.json',
        ROOT/'abi/gem-interactive.json',ROOT/'abi/gem-vdi.json',ROOT/'abi/input.json',
        ROOT/'tests/programs/gem_interactive_launcher.act',ROOT/'tests/programs/gem_interactive_probe.c',ROOT/'tools/build_gem_interactive.py',
        ROOT/'tools/generate_gem_interactive.py',*ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h'),
        *ROOT.glob('lib/display/*'),*ROOT.glob('lib/input/*')]
    foreign['provenance'].update(slice='I4',hardware_execution=True,local_inputs=local_inputs(),
        extraction=extraction,diagnostic=instrument,
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(paths)) if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
        for name in ('main','stage','rootValue','boot','ExecDisplayEntries','ExecInputEntries')))
    (output/'gemcontrol.act').write_text((ui/'gemcontrol.act').read_text())
    source=output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_interactive_launcher.act',{'c-image.inc':include}))
    media=output/'media'; media.mkdir(exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes((i&255)^0x5a for i in range(2048)))
    make(output/'system.atr',media,binary_names={'DATA.BIN'})
    mounts=validate_mounts([dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=SDFS)])
    p=build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
            tasks=True,task_capacity=8,console=True,foreign_image=foreign,dos_mounts=mounts)
    return p,foreign

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--no-opt',action='store_true')
    p.add_argument('--production',action='store_true'); args=p.parse_args()
    program,_=build_interactive(args.output,not args.no_opt,not args.production)
    print(program['xex'])
