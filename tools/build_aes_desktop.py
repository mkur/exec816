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


def build_proof(out, load=False, pointer=False):
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
    launcher=prepare(source,out,foreign,desktop=True,aes=True)
    program=build(compiler(ROOT/'build/actionc'),launcher,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2)])
    from generate_desktop import ABI
    program['build']['desktop_pointer_pixels_per_step']=ABI['constants']['POINTER_PIXELS_PER_STEP']
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--load',action='store_true',help='Start continuous GEM exchange for matched native feedback observations')
    p.add_argument('--pointer',action='store_true',help='Use the AS0 raw-event window for matched pointer observation')
    args=p.parse_args();build_proof(args.output.resolve(),args.load,args.pointer)
