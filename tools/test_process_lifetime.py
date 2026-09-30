#!/usr/bin/env python3
"""Focused P1 emitted-code lifecycle, rollback and capacity regression."""
from library_paths import library_file, read_source
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())


def overrides(out):
    """Record isolated fault injection; production modules have no test switches."""
    edits = {
        'process.act': [
            ('  process.arguments=EXEC.AllocMem(SIZE(length)+1,EXEC.MEMF_UPPER)',
             '  IF PROCESSCONTROL.fault<>1 THEN\n'
             '    process.arguments=EXEC.AllocMem(SIZE(length)+1,EXEC.MEMF_UPPER)\n  FI'),
            ('PROCESSSTATE.Entry POINTER FUNC Control(BYTE operation BYTE POINTER argument)\n',
             'PROCESSSTATE.Entry POINTER FUNC Control(BYTE operation BYTE POINTER argument)\n'
             '  PROCESSSTATE.Entry POINTER row,accepted\n  LONGCARD savedMask\n'
             '  IF operation=PROCESSSTATE.OP_LAUNCH AND PROCESSCONTROL.fault=4 THEN\n'
             '    row=PROCESSSTATE.Entry POINTER(argument)\n    savedMask=row.mask\n    row.mask=0\n'
             '    accepted=PROCESSSTATE.Entry POINTER(DOSCORE.Control(operation,argument))\n'
             '    row.mask=savedMask\n    RETURN(accepted)\n  FI\n')],
        'dosclient.act': [
            ('  client=ClientContext POINTER(EXEC.AllocMem(CLIENT_SIZE,EXEC.MEMF_UPPER\n      OR EXEC.MEMF_CLEAR))',
             '  IF PROCESSCONTROL.fault=2 THEN client=ClientContext POINTER(0)\n'
             '  ELSE client=ClientContext POINTER(EXEC.AllocMem(CLIENT_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR)) FI')],
        'portcore.act': [
            ('  port=EXEC.MsgPort POINTER(EXEC.AllocMem(EXEC.MSGPORT_SIZE,EXEC.MEMF_PUBLIC OR EXEC.MEMF_CLEAR))',
             '  IF PROCESSCONTROL.fault=3 THEN port=EXEC.MsgPort POINTER(0)\n'
             '  ELSE port=EXEC.MsgPort POINTER(EXEC.AllocMem(EXEC.MSGPORT_SIZE,EXEC.MEMF_PUBLIC OR EXEC.MEMF_CLEAR)) FI'),
            ('  bit=EXEC.AllocSignal($ff)',
             '  IF PROCESSCONTROL.fault=5 THEN bit=$ff\n  ELSE bit=EXEC.AllocSignal($ff) FI')],
    }
    hashes = {}
    for name, replacements in edits.items():
        text = read_source(library_file(name))
        text = text.replace('USE EXEC\n','USE EXEC\nUSE PROCESSCONTROL\n',1)
        for old, new in replacements:
            require(text.count(old) == 1, 'Stale Process fault injection: '+name)
            text = text.replace(old,new)
        path = out/name
        path.write_text(text)
        hashes[name] = sha256(path)
    return hashes


def run(out, mode):
    out.mkdir(parents=True,exist_ok=True)
    modified = overrides(out)
    program = build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/process_lifetime.act',out,
                    optimize=mode == 'opt',tasks=True,task_capacity=8,console=False)
    return exercise(program,mode,modified)


def exercise(program, mode, modified):
    out = program['output']
    snapshots = []
    def inspect_entries(bridge):
        for label in ('general_task_start','general_finalizer_start'):
            address = program['labels'][label]
            bridge.bp_set(address,condition='db($2023)=1')
            run_to(bridge,address,frame_limit=4000,timeout=60,condition='db($2023)=1')
            registers = bridge.regs()
            require(int(registers['P'].lstrip('$'),16)&0x3c == 0, 'Invalid Process entry/return width, decimal or IRQ state')
            snapshots.append(dict(routine=label,address=address,registers=registers))
            bridge.bp_clear_all()
    with emulator(ROOT/'build/shell-console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as bridge:
        machine = verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:
            runtime,_ = execute(bridge,program,before_run=inspect_entries,timeout=180,frame_limit=9000)
        except Exception:
            print('Process state:',{name:data(bridge,program['image'],name,True) for name in ('checks','iteration','entered','completed')},bridge.memdump(0x2000,64).hex(),flush=True)
            raise
        for prefix in ('M_PROCESS_RUN_','M_PROCESS_FINISH_','M_PROCESSLIFETIME_CHILD_'):
            routine = next(r for r in program['image']['routines'] if r['name'].startswith(prefix))
            require(routine['address'] >= 65536, 'Process entry must exercise nonzero PBR')
        ownership(bridge,program,out)
        require(data(bridge,program['image'],'completed',True) == [268], 'Missing command lifetimes')
        require(runtime['created'] == 273, 'Missing setup-failure or ordinary Task lifetimes')
        from banked_test_memory import read
        storage = program['build']['memory']['process_storage']
        table = read(bridge,storage['BASE'],storage['TABLE_BYTES'],out)
        require(table == bytes(8*128), 'Process lease or completion storage remains owned')
        return dict(status='pass',mode=mode,build=program['build'],machine=machine,
                    runtime=runtime,checks=data(bridge,program['image'],'checks',True),
                    entry_contexts=snapshots,fixture_overrides=modified,
                    fixture_sha256=sha256(ROOT/'tests/programs/process_lifetime.act'),
                    runner_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=0),
                    process_static_upper_bytes=1028)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out,args.case)
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Process lifetime passed',args.case,result['checks'],flush=True)
