#!/usr/bin/env python3
"""Emitted guard/domain rejection and screen-packet allocation rollback."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def fixture(out, group):
    if group == 'allocation':
        from test_sdx_edx import fixture as editor
        source, payload = editor(out)
        text = source.read_text()
        begin = text.index('  ; Hold slot zero')
        end = text.index('  DOS.SelectInput(oldInput)', begin)
        text = text[:begin] + text[end:]
        text = text.replace('Require(primary=0 AND secondary=0)',
                            'Require(primary=20 AND secondary=103)')
        text = text.replace('state.screen=NULL AND state.screenOpen=0',
                            'state.screen=NULL AND state.screenOpen=0 AND state.screenSpans=NULL')
        source.write_text(text)
        screen = out / 'sdxscreen.act'
        text = screen.read_text()
        needle = 'state.screenSpans=EXEC.AllocMem(300,EXEC.MEMF_UPPER)'
        assert text.count(needle) == 1
        screen.write_text(text.replace(needle, 'state.screenSpans=NULL'))
        return source, payload, True
    text = (ROOT / 'tests/programs/sdx_rawcon.act').read_text()
    text = text.replace('USE A816MEMORY', 'USE A816MEMORY\nUSE SDXCONFIG')
    text = text.replace('BYTE POINTER backing,frame,binding',
                        'BYTE POINTER backing,frame,binding,canary,nativeDp')
    text = text.replace('BYTE flags', 'BYTE flags\n  BYTE ARRAY saved(4)\n  CARD underflowEvent')
    text = text.replace('FOR value=0 TO 255 DO', 'FOR value=0 TO 0 DO')
    begin = text.index('  frame=SDXSTATE.GetFrame(state)\n  SDXSTATE.Word(frame,SDXABI.FRAME_PC,$3000)\n  state.dp($54)=30')
    text = text[:begin] + '''  nativeDp=BYTE POINTER(ADDRESS(SDXSTATE.ReadWord(state.context,SDXABI.FIELDS_NATIVE_D)))
  FOR index=0 TO 3 DO
    saved(index)=nativeDp(index)
    nativeDp(index)=BYTE($31+index)
  OD
  FOR index=0 TO 31 DO
    frame=SDXSTATE.GetFrame(state)
    SDXSTATE.Word(frame,SDXABI.FRAME_PC,$3000)
    frame(SDXABI.FRAME_A)=123
    state.dp($54)=29
    state.dp($55)=79
    state.screen(2399)=77
    canary=BYTE POINTER(ADDRESS(SDXCONFIG.DP_BASE-16+index))
    IF index>=16 THEN
      canary=BYTE POINTER(ADDRESS(SDXCONFIG.DP_BASE+512+index-16))
    FI
    canary(0)=$a4
    Require(SDXRUNTIME.Run(0)=SDXABI.RAWCON_EVENT+4)
    canary(0)=$a5
    Require(state.screen(2399)=77)
  OD
  frame=SDXSTATE.GetFrame(state)
  SDXSTATE.Word(frame,SDXABI.FRAME_PC,$3000)
  frame(SDXABI.FRAME_A)=$cf
  state.screenFirst(29)=80
  state.screenEnd(29)=0
  Require(SDXRUNTIME.Run(0)=SDXABI.CHECKPOINT_EVENT)
  Require(state.screen(2399)=$cf AND state.screenFirst(29)=79 AND state.screenEnd(29)=80)
  frame=SDXSTATE.GetFrame(state)
  frame(SDXABI.FRAME_A)=0
  Require(SDXRUNTIME.Run(0)=SDXABI.CHECKPOINT_EVENT)
  frame=SDXSTATE.GetFrame(state)
  Require(frame(SDXABI.FRAME_A)=$cf AND (frame(SDXABI.FRAME_P) & $82)=$80)
  FOR index=0 TO 3 DO
    Require(nativeDp(index)=BYTE($31+index))
    nativeDp(index)=saved(index)
  OD
''' + text[begin:]
    needle = '''  SDXRUNTIME.Unbind(0)
  Require(SDXSTATE.ReadWord(binding,SDXABI.BINDING_OWNER)=0)
  SDXRUNTIME.Release()'''
    assert text.count(needle) == 1
    text = text.replace(needle, '''  pending=0
  frame=SDXSTATE.GetFrame(state)
  SDXSTATE.Word(frame,SDXABI.FRAME_PC,$3000)
  ; LDX #$6c; TXS; JSR RAWCON put produces complete S=$015f.
  state.bank($3000)=$a2
  state.bank($3001)=$6c
  state.bank($3002)=$9a
  state.bank($3003)=$20
  state.bank($3004)=$80
  state.bank($3005)=$f6
  A816MEMORY.Fill(BYTE POINTER(ADDRESS($130)),$a5,32)
  underflowEvent=SDXRUNTIME.Run(0)
  ; No invalid anchor is lent to another native operation after observation.
  SDXRUNTIME.Release()
  Require(underflowEvent=SDXABI.RAWCON_EVENT+4)
  Require(SDXSTATE.ReadWord(state.context,SDXABI.FIELDS_GUEST_S)=$15f)
  Require(state.screen(2399)=77)
  canary=BYTE POINTER(ADDRESS($130))
  FOR index=0 TO 31 DO
    Require(canary(index)=$a5)
  OD
  Require(SDXSTATE.ReadWord(binding,SDXABI.BINDING_OWNER)=0)''')
    source = out / 'failures.act'
    source.write_text(text)
    return source, [], False


def run(out, group):
    out.mkdir(parents=True, exist_ok=True)
    source, payload, console = fixture(out, group)
    profile = json.loads((ROOT / 'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 16384
    memory = out / 'memory-profile.json'
    memory.write_text(json.dumps(profile))
    program = build(compiler(ROOT / 'build/actionc', release=True), source, out,
                    tasks=True, task_capacity=12, console=console, console_test=not console, sdx=True,
                    image_data=payload, memory_profile=memory,
                    dos_mounts=[dict(alias='RAM', format=3)] if console else [])
    with emulator(ROOT / 'build/shell-paced-bridge',
                  ROOT / 'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, program, timeout=180, frame_limit=9000)
        except Exception:
            print('Checks:', data(b, program['image'], 'checks'), flush=True)
            raise
        ownership(b, program, out)
        checks = int.from_bytes(bytes(data(b, program['image'], 'checks')), 'little')
    return dict(status='pass', tier='development', qualification=False, group=group,
                checks=checks, runtime=runtime, machine=machine, build=program['build'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('guards', 'allocation'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.group)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('RAWCON', args.group, result['checks'], 'checks passed')
