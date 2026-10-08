#!/usr/bin/env python3
"""Matched native-panel/counter workload, with development-only observation hooks."""
import argparse,json
from pathlib import Path
from build_aes_desktop import counter_image,counter_bindings
from build_desktop_input import fixture
from build_bitmap_console import prepare
from generate_memory import PROFILE
from native_program import ROOT,build,compiler


def build_coexist(out):
    out.mkdir(parents=True,exist_ok=True)
    foreign=counter_image(out,True)
    source=fixture(out,True).read_text().replace('USE DESKAPP\n','USE DESKAPP\nUSE AESBOOT\n')
    source=source.replace('BYTE holdEvents','BYTE startGate,runCounters\nBYTE holdEvents')
    begin=source.index('  DESKTOP.Prepare(@control,DESKTYPES.OPEN)')
    end=source.index('  previousMode=0',begin)
    source=source[:begin]+source[end:]
    source=source.replace('  ready=1', '''  ready=1
  WHILE startGate=0 DO
    ignored=EXECTASKS.Sleep(1)
  OD

  IF runCounters<>0 THEN
    Require(CountersStart()<>0)
  FI

  ready=2''')
    source=source.replace('  DESKAPP.Stop()\n  Send(DESKTYPES.CLOSE,panel)', '''  IF runCounters<>0 THEN
    Require(CountersStop()<>0)
  FI

  DESKAPP.Stop()''')
    # Mode 4's test-owned window is intentionally absent: shell, production
    # panel and two counters consume all four desktop layers.
    begin=source.index('      IF mode=4 THEN');end=source.index('      previousMode=mode',begin)
    source=source[:begin]+source[end:]
    source=source.replace('  ready=2\n\nRETURN','  ready=3\n\nRETURN')
    path=out/'coexist.act';path.write_text(counter_bindings(source,foreign))
    # Marker identity is checked against admitted GEM handles by the runner.
    gui=(ROOT/'lib/aes/aesgui.act').read_text()
    routines='CARD diagnosticNotice\n\n'
    for i in (1,2):
        routines+=f'PROC Notice{i}()\n\n  diagnosticNotice={i}\n\nRETURN\n\n'
    gui=gui.replace('; Close/reopen',routines+'; Close/reopen',1)
    gui=gui.replace('  EXEC.PutMsg(endpoint.port,@delivery.delivery.message)', '''  IF client.gui.window=1 THEN
    Notice1()
  ELSEIF client.gui.window=2 THEN
    Notice2()
  FI

  EXEC.PutMsg(endpoint.port,@delivery.delivery.message)''')
    (out/'aesgui.act').write_text(gui)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    launcher=prepare(path,out,foreign,desktop=True,aes=True)
    program=build(compiler(ROOT/'build/actionc'),launcher,out/'program',tasks=True,task_capacity=8,
        foreign_image=foreign,console_deferred=True,memory_profile=memory,stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2)])
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse']=metadata(None)
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    build_coexist(p.parse_args().output.resolve())
