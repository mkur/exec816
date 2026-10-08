#!/usr/bin/env python3
"""Resident GEM Control Panel and counter, using ordinary application bindings."""
import argparse,json
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT,build,compiler


def build_desktop(out,source=None,program_output=None,files=False,disk_component=False,**options):
    from library_paths import read_source
    from build_gem_input import input_bindings
    from c_program import ABI,binding
    out.mkdir(parents=True,exist_ok=True)
    options.pop('desktop',None)
    foreign=drawing(out,True,widgets=True,client_sources=[
        ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
        ROOT/'c/calypsi/program.c',
        ROOT/'examples/gem-panel/panel.c',ROOT/'examples/gem-panel/resident.c',
        ROOT/'examples/gem-counter/counter.c',ROOT/'examples/gem-browser/browser.c'],
        client_entries=['GEMPanelTask','GEMCounterTask','GEMBrowserTask'],
        client_roots=['GEMDesktopStart','GEMDesktopStop','GEMDesktopService','GEMPanel','GEMCounter','GEMBrowser','GEMDesktopFiles','ExecProgramRun',*ABI['imports']],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_panel_layout.c',[
                ('Panel size',400),('Panel ready',8),('Panel actions',10),('Panel paints',14),
                ('Panel work',34),('Panel tree',178),('Panel status',370),('Panel focus',392),('Panel armed',394)]),
            (ROOT/'tests/programs/gem_browser_layout.c',[('Browser size',1992),('Browser ready',8),('Browser work',26),
                ('Browser tree',170),('Browser path',178),('Browser names',306),('Browser status',1386),
                ('Browser count',1962),('Browser selected',1966),('Browser launches',1972),('Browser child',1980)])])
    binding(foreign,out)
    if disk_component:
        from gem_component import prepare as prepare_component
        prepare_component(foreign,out)
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    # Reuse the existing two-call Action!/C startup binding without adding a
    # public lifecycle abstraction to GEM applications.
    aliases=dict(foreign);aliases['symbols']=dict(foreign['symbols'])
    for suffix in ('Service','Start','Stop'):
        aliases['symbols']['GEMInputs'+suffix]=foreign['symbols']['GEMDesktop'+suffix]
    text=read_source(source or ROOT/'tests/programs/gem_desktop_session.act')
    text=input_bindings(text,aliases).replace('InputsStart','DesktopStart').replace('InputsStop','DesktopStop')
    if files:
        text=text.replace('BYTE FUNC DesktopStart()\n',f'BYTE FUNC DesktopStart()\n\n  LET files=CARD POINTER(${foreign["symbols"]["GEMDesktopFiles"]:x})\n  files^=1\n')
    source=out/'gem-session.act';source.write_text(text)
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
    args=parser.parse_args()
    build_desktop(args.output.resolve(),stack_checks=True)
