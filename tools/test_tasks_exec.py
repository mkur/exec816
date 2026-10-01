#!/usr/bin/env python3
"""Qualify classic Task policy through emitted code on pinned AltirraOS."""
import adapter_state as adapter
import argparse
import json
import struct
from pathlib import Path

from native_program import ROOT, build, command, compiler, execute, platform_files, require, sha256, verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import data
from generate_tasks import ABI


def pointer_values(bridge,image,name):
    raw = bytes(data(bridge,image,name))
    return [int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]


def check_core(bridge,program,result):
    image = program['image']
    abi = ABI
    observed = {'checks':data(bridge,image,'checks',True),
                'progress':data(bridge,image,'progress'), 'pointers':pointer_values(bridge,image,'pointers')}
    require(observed['checks'] == [abi['version'],128,0,1,1,0,0,0], 'Core Task checks: '+str(observed))
    require(observed['progress'] == [1,1,2], 'Task entry/finalizer did not complete: '+str(observed))
    objects = next(d for d in image['data'] if '_WORKERS_' in d['name'])
    pointers = observed['pointers']
    expected = [objects['address']+i*abi['task']['size'] for i in range(3)]
    require(pointers[1:4] == expected and pointers[4] in expected and pointers[0] not in expected,
            'Task identity is not a full public pointer')
    raw = bytes(data(bridge,image,'workers'))
    for i in range(3):
        offset = i*abi['task']['size']
        require(raw[offset+12:offset+15] == bytes([6,255,255]), 'Removal state/nesting mismatch')
    require(result['created'] == 3 and result['vbi_dispatches'] > 0 and result['os_calls'] == 1,
            'Missing admission, preemption or OS operation')
    return observed


def check(bridge,program,fixture,result):
    abi = ABI
    if fixture == 'core':
        observed = check_core(bridge,program,result)
    elif fixture == 'faults':
        observed = {'reached':data(bridge,program['image'],'reached')}
        require(observed['reached'] == [0], 'Misuse returned to its caller')
    elif fixture == 'sleep':
        observed = {'checks':data(bridge,program['image'],'checks',True)}
        r = observed['checks']
        require(r[0] >= 0xfffd and r[1] == 0 and 4 <= r[2] < 128 and
                r[3:9] == [1,4,0xff12,0xff18,1,3] and 25 <= r[9] < 128 and
                r[10:] == [4,0], 'Sleep/cancellation: '+str(r))
        require(result['created'] == 2, 'Sleeping slot not reused')
    elif fixture == 'far':
        observed = {'checks':data(bridge,program['image'],'checks',True)}
        require(observed['checks'] == [1,1,1,0,0,0,0,1,1,1,255,4], 'Far Task: '+str(observed))
        require(data(bridge,program['image'],'previous') == [255]+list(range(255)), 'Priority byte result mismatch')
        from banked_test_memory import read as far_read
        raw = far_read(bridge,0x04ffe0,96,program['output'])
        require(raw[:15] == bytes([0xa5])*15 and raw[15+abi['task']['size']:] == bytes([0xa5])*(len(raw)-15-abi['task']['size']), 'Far Task guard changed')
        observed['far_task_bytes'] = raw.hex()
    else:
        observed = {'checks':data(bridge,program['image'],'checks',True)}
        expected = {'admission':[1]*22, 'reuse':[1,6,255,0,0,0,260,0],
                    'root':[2,6,1,3,1,1]}[fixture]
        require(observed['checks'] == expected, fixture+': '+str(observed))
        require(result['created'] == {'admission':4,'reuse':261,'root':2}[fixture], 'Admission count mismatch')
    if result['status'] == 0:
        # Self-removal clears the binding and nesting, then requests a switch
        # through caller.pending. That bit may remain set in the retired slot.
        require(all(r[:3] == [0]*3 and r[10:12] == [0]*2 and r[12] in (0,1) and r[26:29] == [0]*3
                    and r[30:32] == [0]*2 for r in result['task_records'][:4]),
                'Removed Task binding, nesting or deadline leaked')
    flags = program['build']['probe_flags']
    if flags != 0x100:
        observed['contexts'] = []
        for slot,pool in enumerate(abi['pools'][:4]):
            raw = bridge.memdump(adapter.PROBE0+slot*32,24)
            expected = struct.pack('<BHHHHBHHHHH',0x12,pool['dp'],
                0x78 if flags & 0x10 else 0x5678,0x34 if flags & 0x10 else 0x1234,
                0xab01,flags,pool['stack_base']+0x5f8,0xbeef,0xff10,0xff11,0xff10)
            require(raw[:20] == expected, f'Task {slot} context: {raw.hex()}')
            before,after = struct.unpack('<HH',raw[20:])
            require(before == after if slot == 0 or flags & 4 else after > before, 'I-mask dispatch mismatch')
            observed['contexts'].append(raw.hex())
    c = program['build']['memory']['constants']
    table = bridge.memdump(c['TABLE'],c['TABLE_BYTES'])
    manifest = (program['output']/'manifest.bin').read_bytes()
    require(table == manifest[32:32+c['TABLE_BYTES']], 'Task lifetime released image banks')
    observed['bank_table'] = table.hex()
    return observed


def raw_probe(toolchain,program,variant):
    image,output = program['image'],program['output']
    entry = image['entry']
    labels = {name:next(d['address'] for d in image['data'] if '_'+symbol+'_' in d['name'])
              for name,symbol in [('CHECKS','RAWCHECKS'),('REACHED','REACHED')]}
    config = output/'raw.cfg'
    config.write_text(f'MEMORY {{ RAM: start=${entry:x}, size=$1000, file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-D',f'VARIANT={variant}','-D',f'TASK_ABI_TAG={ABI["constants"]["PROFILE_TAG"]}',*[arg for name,value in labels.items() for arg in ('-D',f'{name}={value}')],
             '-o',output/'raw.o',ROOT/'tests/programs/tasks_exec_raw.s'])
    command(['ld65','-C',config,'-o',output/'raw.bin',output/'raw.o'])
    raw = list((output/'raw.bin').read_bytes())
    segment = next(s for s in image['segments'] if s['address'] == entry)
    require(len(raw) <= len(segment['bytes']), 'Raw probe exceeds Main extent')
    segment['bytes'][:len(raw)] = raw
    from test_banked import changed_image
    changed_image(program)
    program['build']['raw_task_probe'] = variant
    program['build']['raw_task_probe_sha256'] = sha256(ROOT/'tests/programs/tasks_exec_raw.s')
    (output/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, required=True)
    parser.add_argument('--bridge-dir', type=Path, required=True)
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/tasks-exec-tests')
    parser.add_argument('--mode', choices=('raw','opt'))
    parser.add_argument('--case', action='append')
    parser.add_argument('--profile', choices=('1x','8x'), default='1x')
    args = parser.parse_args()
    pin = json.loads((ROOT/'toolchain/altirra-signals-1m.json').read_text()) if args.profile=='8x' else PIN
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir,args.rom)
    report = {'schema_version':1,'status':'running','platform':pin,'cases':[],
              'inputs':{str(p.relative_to(ROOT)):sha256(p) for folder in
                  ('tools','lib','abi','platform/altirraos','tests/programs','toolchain')
                  for p in sorted((ROOT/folder).glob('**/*' if folder=='lib' else '*')) if p.is_file()}}
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=pin) as bridge:
            report['emulator_config'] = verify_machine(bridge,args.rom,pin)
            cases = []
            for mode in ('raw','opt'):
                if args.mode and args.mode != mode: continue
                for fixture in ('core','admission','root','sleep','far'):
                    cases.append((fixture+'-'+mode,fixture,mode,0,0x100,None))
                for variant in (*range(6), *range(7,13)):
                    cases.append((f'fault-{variant}-{mode}','faults',mode,0,0x100,variant))
                for point in (9,10,11,12,15,16,17,18):
                    cases.append((f'nmi-{point}-{mode}','core',mode,point,0x100,None))
                for flags in (0xc9,0xd9,0xe9,0xf9,0xcd):
                    cases.append((f'registers-{flags:02x}-{mode}','core',mode,0,flags,None))
            for mode in ('raw','opt'):
                if not args.mode or args.mode == mode:
                    cases.append(('reuse-'+mode,'reuse',mode,0,0x100,None))
            if args.case:
                cases = [c for c in cases if c[0] in args.case]
                require({c[0] for c in cases} == set(args.case), 'Unknown case')
            for name,fixture,mode,point,flags,variant in cases:
                print('Running '+name+'...',flush=True)
                source = 'tasks_exec'+('' if fixture == 'core' else '_'+fixture)+'.act'
                image_data = [(0x04ffe0,bytes([0xa5])*96),(0x05fff0,bytes([0xa5])*32)] if fixture == 'far' else ()
                program = build(toolchain,ROOT/'tests/programs'/source,output/name,
                                optimize=mode=='opt',tasks=True,probe_nmi=point,
                                probe_flags=flags,image_data=image_data)
                before_run = None
                if variant is not None:
                    address = next(d['address'] for d in program['image']['data'] if '_VARIANT_' in d['name'])
                    before_run = lambda b:b.poke(address,variant)
                    if variant >= 6:
                        raw_probe(toolchain,program,variant)
                try:
                    result,screen = execute(bridge,program,frame_limit=12000 if fixture == 'reuse' else 1800,
                                            timeout=1200 if fixture == 'reuse' else 180,expected_status=(3 if variant == 5 else 4) if variant is not None else 0,
                                            before_run=before_run,timer_irq=fixture == 'far')
                    observed = check(bridge,program,fixture,result)
                    if point == 18:
                        require(result['vbi_count'] > result['native_nmi_count'], 'No emulation-mode VBI')
                    if fixture == 'far':
                        require(result['native_irq_count'] > 0, 'No timer IRQ stimulus')
                except Exception:
                    (program['output']/'failure.json').write_text(json.dumps({
                        'regs':bridge.regs(),'state':bridge.memdump(adapter.STATE,64).hex(),
                        'private':bridge.memdump(0x2d00,240).hex(),'globals':bridge.memdump(0x8800,1024).hex()},indent=2)+'\n')
                    raise
                report['cases'].append({'name':name,'status':'pass','build':program['build'],
                                        'runtime':result,'observed':observed})
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed '+str(len(report['cases']))+' classic Task cases')


if __name__ == '__main__':
    main()
