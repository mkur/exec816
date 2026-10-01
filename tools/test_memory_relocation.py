#!/usr/bin/env python3
"""Development checks for relocated state/globals and retired boot storage."""
import argparse
import json
import struct
from pathlib import Path

import adapter_state as adapter
from native_program import ROOT, build, compiler, execute, platform_files, require, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-signals-1m.json').read_text())


def stop_at(bridge, address):
    bridge.bp_clear_all()
    bridge.bp_set(address)
    run_to(bridge, address, frame_limit=3000, timeout=90)
    bridge.bp_clear_all()


def load(bridge, program, memlo=None):
    bridge.bp_clear_all()
    bridge.boot(str(program['xex']))
    if memlo is not None:
        stop_at(bridge, program['labels']['loader_init'])
        bridge.memload(0x2e7, struct.pack('<H', memlo))
    stop_at(bridge, program['labels']['loader_start'])
    stop_at(bridge, program['labels']['start'])


def retired_case(bridge, program, memlo=None):
    c = program['build']['memory']['constants']
    load(bridge, program, memlo)
    observed = {}

    def symbol(name):
        return next(d['address'] for d in program['image']['data'] if '_'+name.upper()+'_' in d['name'])

    def retire(b):
        b.poke(symbol('hostInput'),0x5a)
        require(b.peek(c['RETIRED']) == b'\0', 'Retirement survived a cold boot')
        require(b.peek16(c['MANIFEST']+4) == 1, 'Cold boot did not reload manifest')
        b.memload(0x2000, bytes([0x6d])*256)
        b.memload(0x8800, bytes([0x97])*2048)
        stop_at(b, program['labels']['startup_complete'])
        require(b.peek(c['RETIRED']) == b'\1' and b.peek16(c['ADOPTED']) == 1,
                'Startup did not publish successful retirement')
        b.memload(c['MANIFEST'], bytes([0xd3])*2048)
        # Every manifest validation field is now invalid. Repeated adoption
        # executes below; any traversal of its validation path must fail.
        observed['stale_reader_check'] = 'All identity, count and seed bytes poisoned before repeat Adopt/Init'
        observed['manifest_poisoned_at'] = program['labels']['startup_complete']
        condition = f'dw(${symbol("checks"):x})>=258'
        point = program['labels']['native_nmi']
        b.bp_set(point,condition=condition)
        run_to(b,point,3000,60,condition)
        b.bp_clear_all()
        before = b.regs()
        b.poke(symbol('hostGate'),0xa6)
        after = b.regs()
        require(all(before[k] == after[k] for k in ('PC','A','X','Y','S','P')),
                'Far stimulus changed paused registers')
        require(b.peek(symbol('hostGate')) == bytes([0xa6]), 'Far stimulus did not write upper RAM')
        observed['far_stimuli'] = ['bootstrap','native-nmi']

    try:
        runtime, _ = execute(bridge, program, preloaded=True, before_run=retire,
                             frame_limit=3000, timeout=180)
    except Exception:
        print({name:data(bridge,program['image'],name) for name in
               ('finished','checks','values','parent','alias')},flush=True)
        raise
    require(data(bridge, program['image'], 'finished') == [2], 'Fixture did not finish')
    values = int.from_bytes(bytes(data(bridge,program['image'],'values')),'little')
    require([bridge.eval_expr(f'db(${values+i:x})') for i in range(4)] == [17,34,99,68],
            'Upper array/pointer mutation failed')
    require(runtime['vbi_dispatches'] > 0 and runtime['created'] == 1,
            'No preempted Task lifetime')
    for address, size, value in ((0x2000,256,0x6d),(0x8800,2048,0x97),(c['MANIFEST'],2048,0xd3)):
        require(bridge.memdump(address,size) == bytes([value])*size, f'Retired bytes changed at ${address:x}')
    table = bytes(bridge.eval_expr(f'db(${c["TABLE"]+i:x})') & 255 for i in range(c['TABLE_BYTES']))
    require(table == (program['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']],
            'Shutdown did not restore heap ownership')
    observed.update(checks=data(bridge,program['image'],'checks',True)[0],
                    retired_ranges_intact=True, table_restored=True, runtime=runtime)
    return observed


def rejection_cases(bridge, program):
    c = program['build']['memory']['constants']
    observed = []
    # Loader must reject before touching the newly claimed adapter page.
    bridge.bp_clear_all()
    bridge.boot(str(program['xex']))
    stop_at(bridge, program['labels']['loader_init'])
    bridge.memload(adapter.STATE, bytes([0x73])*256)
    bridge.memload(0x2e7, struct.pack('<H', 0x801))
    stop_at(bridge, program['labels']['loader_start'])
    stop_at(bridge, program['labels']['loader_done'])
    require(bridge.peek(program['labels']['loader_error']) == b'\1', 'Loader accepted high MEMLO')
    require(bridge.memdump(adapter.STATE,256) == bytes([0x73])*256, 'Loader rejection wrote state')
    observed.append('loader-memlo-0801')

    # Exercise the hosted preflight independently of the earlier loader check.
    load(bridge, program)
    vectors = bridge.memdump(0x256,9)
    bridge.memload(adapter.STATE, bytes([0x73])*256)
    bridge.memload(c['OLD_MEMLO'], struct.pack('<H', 0x801))
    stop_at(bridge, program['labels']['state_rejected'])
    require(bridge.memdump(adapter.STATE,256) == bytes([0x73])*256 and
            bridge.memdump(0x256,9) == vectors, 'Hosted rejection changed unclaimed storage/vectors')
    observed.append('hosted-memlo-0801')

    load(bridge, program)
    bridge.memload(c['MANIFEST']+4, b'\0\0')
    stop_at(bridge, program['labels']['done'])
    require(bridge.peek16(adapter.STATUS) == 4, 'Invalid first adoption succeeded')
    require(bridge.peek16(c['ADOPTED']) == 0 and bridge.peek(c['RETIRED']) == b'\0',
            'Failed adoption retired the manifest')
    observed.append('invalid-first-adoption')
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'build/memory-relocation')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir,args.rom)
    report = dict(tier='development',status='running',pin=PIN,cases=[])
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge,args.rom,PIN)
            for name, optimized, checkpoint in (('raw',False,0),('opt',True,0),('nmi-stack',True,3)):
                print('Running relocation '+name+'...',flush=True)
                program = build(toolchain,ROOT/'tests/programs/memory_relocation.act',output/name,
                                optimize=optimized,tasks=True,task_capacity=8,probe_nmi=checkpoint)
                observed = retired_case(bridge,program,memlo=0x800)
                report['cases'].append(dict(name=name,status='pass',build=program['build'],observed=observed))
                if name == 'opt':
                    report['rejections'] = rejection_cases(bridge,program)
                    report['cold_restart'] = retired_case(bridge,program)
            simple = build(toolchain,ROOT/'examples/hello.act',output/'direct',optimize=True)
            bridge.bp_clear_all()
            bridge.boot(str(simple['xex']))
            stop_at(bridge,simple['labels']['start'])
            bridge.memload(adapter.STATE,bytes([0x73])*256)
            bridge.memload(0x2e7,struct.pack('<H',0x801))
            stop_at(bridge,simple['labels']['state_rejected'])
            require(bridge.memdump(adapter.STATE,256) == bytes([0x73])*256,'Direct rejection wrote state')
            report['rejections'].append('direct-xex-memlo-0801')
            bridge.bp_clear_all()
            bridge.boot(str(simple['xex']))
            stop_at(bridge,simple['labels']['start'])
            bridge.memload(0x2e7,struct.pack('<H',0x800))
            report['direct_boundary'],_ = execute(bridge,simple,preloaded=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Memory relocation development checks passed')


if __name__ == '__main__':
    main()
