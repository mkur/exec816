#!/usr/bin/env python3
"""Resident GEM Control Panel and counter, using ordinary application bindings."""
import argparse,json
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT,build,compiler


def build_desktop(out,source=None,program_output=None,**options):
    from library_paths import read_source
    from build_gem_input import input_bindings
    out.mkdir(parents=True,exist_ok=True)
    options.pop('desktop',None)
    foreign=drawing(out,True,widgets=True,client_sources=[
        ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
        ROOT/'examples/gem-panel/panel.c',ROOT/'examples/gem-panel/resident.c',
        ROOT/'examples/gem-counter/counter.c'],
        client_entries=['GEMPanelTask','GEMCounterTask'],
        client_roots=['GEMDesktopStart','GEMDesktopStop','GEMDesktopService','GEMPanel','GEMCounter'],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_panel_layout.c',[
                ('Panel size',400),('Panel ready',8),('Panel actions',10),('Panel paints',14),
                ('Panel work',34),('Panel tree',178),('Panel status',370),('Panel focus',392),('Panel armed',394)])])
    # Reuse the existing two-call Action!/C startup binding without adding a
    # public lifecycle abstraction to GEM applications.
    aliases=dict(foreign);aliases['symbols']=dict(foreign['symbols'])
    for suffix in ('Service','Start','Stop'):
        aliases['symbols']['GEMInputs'+suffix]=foreign['symbols']['GEMDesktop'+suffix]
    text=read_source(source or ROOT/'tests/programs/gem_desktop_session.act')
    text=input_bindings(text,aliases).replace('InputsStart','DesktopStart').replace('InputsStop','DesktopStop')
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
