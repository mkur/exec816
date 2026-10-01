#!/usr/bin/env python3
"""Qualify INITAD loading, bank policy and banked preemption on pinned Altirra."""
import adapter_state as adapter
from library_paths import read_source
from native_abi import FIELDS
import argparse
import copy
import json
from pathlib import Path
import struct
import sys

from native_program import (ROOT, compiler, build, command, execute, verify_machine,
                            platform_files, require, xex_segment, sha256)
from os_boundary import emulator, run_to
from generate_memory import layout, generate
from banked_image import emit
from banked_test_memory import read as far_read, write as far_write
from test_cooperative import data
from test_preemptive import check as check_preemptive

PIN = json.loads((ROOT/'toolchain/altirra-1m.json').read_text())


def xex_segments(blob):
    require(blob[:2] == b'\xff\xff', 'Bad test XEX magic')
    pos = 2
    result = []
    while pos < len(blob):
        start,end = struct.unpack_from('<HH',blob,pos)
        pos += 4
        require(end >= start and pos+end-start+1 <= len(blob), 'Malformed test XEX')
        result.append((start,blob[pos:pos+end-start+1]))
        pos += end-start+1
    return result


def write_xex(path, segments):
    path.write_bytes(b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in segments))


def assemble_probe(output, source, origin=0x3000):
    output.mkdir(parents=True,exist_ok=True)
    (output/'probe.s').write_text(source)
    (output/'probe.cfg').write_text(
        f'MEMORY {{ RAM: start=${origin:x}, size=$2000, file=%O; }} '
        'SEGMENTS { CODE: load=RAM, type=ro; }\n')
    command(['ca65','-o',output/'probe.o',output/'probe.s'])
    command(['ld65','-C',output/'probe.cfg','-o',output/'probe.bin',
             '-Ln',output/'probe.lbl',output/'probe.o'])
    labels = {line.split()[2].lstrip('.'):int(line.split()[1],16)
              for line in (output/'probe.lbl').read_text().splitlines()}
    write_xex(output/'probe.xex', [(origin,(output/'probe.bin').read_bytes()),
                                 (0x2e0,struct.pack('<H',labels['start']))])
    return labels


def profile_probe(bridge, output):
    # Writes all samples first, then reads all of them. Aliasing cannot pass
    # merely because each write was immediately followed by its own read.
    # This isolated probe never enters the hosted kernel or initializes its DP.
    addresses = [(b<<16)|off for b in range(1,16) for off in (0,0x100,0x2100,0xd500,0xffff)]
    lines = ['.setcpu "65816"','.segment "CODE"','.export start,done',
             'start:','lda #$5a','sta $2100']
    for i,a in enumerate(addresses):
        lines += [f'lda #{(i*37+11)%256}',f'sta f:${a:06x}']
    for i,a in enumerate(addresses):
        lines += [f'lda f:${a:06x}',f'cmp #{(i*37+11)%256}','beq :+','jmp failed',':']
    lines += ['lda $2100','cmp #$5a','beq :+','jmp failed',':','lda #1','sta $2101',
              'jmp done','failed:','lda #$ff','sta $2101','done:','jmp done']
    labels = assemble_probe(output,'\n'.join(lines)+'\n',0x6000)
    bridge.bp_clear_all(); bridge.boot(str(output/'probe.xex'))
    run_to(bridge,labels['start'])
    rom = bridge.memdump(0xc000,0x1000)+bridge.memdump(0xd800,0x2800)
    bridge.bp_set(labels['done']); run_to(bridge,labels['done'])
    require(bridge.memdump(0x2100,2) == b'\x5a\x01','Upper banks unavailable or aliased')
    require(bridge.memdump(0xc000,0x1000)+bridge.memdump(0xd800,0x2800) == rom,'OS ROM changed')
    return {'banks':list(range(1,16)), 'samples':len(addresses), 'bank_zero_alias_guard':'intact',
            'probe_sha256':sha256(output/'probe.xex')}


def policy_probe(bridge, toolchain, output, count, optimize):
    """Synthetic inventories test policy bounds, independent of physical banks.

    Debugger loading is only for this isolated policy fixture. Production boot
    and the banked integration cases use the actual INITAD transport.
    """
    memory = layout(max_banks=count)
    memory_hash = generate(output,memory)
    (output/'execmemory.act').write_text(read_source(ROOT/'lib/exec/execmemory.act'))
    (output/'banks.act').write_text((ROOT/'tests/programs/banks.act').read_text())
    (output/'layout.json').write_text(json.dumps({'code_origin':0x10000,'data_origin':0x8800,
        'stack_overflow':0x30f0,'nmi_extra_stack':0,'imports':[]}))
    command([toolchain['binary'],'--module-path',output,'--layout',output/'layout.json',
             '-o',output/'program.json',*([] if optimize else ['--no-opt']),output/'banks.act'])
    image = json.loads((output/'program.json').read_text())
    source = f'''.setcpu "65816"
.segment "CODE"
.a8
.i8
.export start,done
start:
    sei
    cld
    stz $d40e
    clc
    xce
    rep #$30
    .a16
    .i16
    lda #${adapter.KERNEL_DP:04x}
    tcd
    lda #$4ffd
    tcs
    sep #$20
    .a8
    lda #0
    sta 1,s
    rep #$20
    .a16
    jsl ${image['entry']:06x}
done:
    jmp done
    .res $f0-(*-start),$ea
    jmp done
'''
    labels = assemble_probe(output,source)
    bridge.bp_clear_all(); bridge.boot(str(output/'probe.xex')); run_to(bridge,labels['start'])
    for segment in image['segments']:
        far_write(bridge,segment['address'],bytes(segment['bytes']),output)
    for zero in image['zero_fill']:
        far_write(bridge,zero['address'],bytes(zero['size']),output)
    c = memory['constants']
    seed = bytearray(c['TABLE_BYTES'])
    seed[:4] = b'\2\0\1\0'
    for bank in range(1,count):
        if bank != 2:
            seed[bank*4] = 1
        # A sparse 256-index inventory tests the last record and scanning past
        # pinned banks. The 16-entry case exhausts a dense inventory. Avoid
        # repeating the same O(N) allocation scan for every synthetic bank.
        if count == 256 and 4 <= bank < 255:
            seed[bank*4:bank*4+4] = b'\2\0\1\0'
    bridge.memload(c['TABLE']-16,bytes([0xa5])*16+seed+bytes([0xa5])*16)
    header = b'EBM1'+struct.pack('<HHH',1,count,0)+bytes(6)+bytes(range(16))
    bridge.memload(c['MANIFEST'],header+seed)
    boot = bytearray(256);boot[0] = 1;boot[16:32] = bytes(range(16))
    bridge.memload(c['READY'],boot)
    bridge.memload(adapter.KERNEL_DP,bytes(256))
    bridge.memload(adapter.KERNEL_DP+FIELDS["owner_pointer"]["offset"],struct.pack('<HBBHH',adapter.KERNEL_OWNER,0,1,0x4b00,0x4fff))
    bridge.memload(0x49f0,bytes([0xa5])*0x620)
    bridge.bp_set(labels['done'])
    try:
        run_to(bridge,labels['done'],frame_limit=12000,timeout=120 if count == 256 else 60)
    except RuntimeError as error:
        progress = {name:data(bridge,image,name,True) for name in ('checks','failures','count','selected')}
        raise RuntimeError(f'{error}; policy progress: {progress}') from error
    failures = data(bridge,image,'failures',True)[0]
    checks = data(bridge,image,'checks',True)[0]
    require(failures == 0 and checks > count*4, f'Bank policy failed: {failures}/{checks}')
    for address in (c['TABLE']-16,c['TABLE']+c['TABLE_BYTES'],0x49f0,0x5000):
        # At MAX_BANKS=256 the table ends at the boot record, not a spare guard.
        if address == c['READY']:
            continue
        require(bridge.memdump(address,16) == bytes([0xa5])*16,f'Policy guard at {address:x}')
    reserved = FIELDS['reserved_zero']
    require(bridge.memdump(adapter.KERNEL_DP+reserved['offset'],reserved['size']) == bytes(reserved['size']),
            'Policy DP reserved bytes changed')
    expected = bytearray(seed)
    if count > 1:
        expected[4:8] = b'\2\0\2\0'
    require(bridge.memdump(c['TABLE'],len(seed)) == expected,'Final bank ownership differs')
    return {'max_banks':count,'optimize':optimize,'checks':checks,'failures':failures,'synthetic_inventory':True,
            'memory_sha256':memory_hash,'image_sha256':sha256(output/'program.json'),
            'probe_sha256':sha256(output/'probe.xex'),'guards':'intact'}


def changed_image(program, probe=False):
    image_path = program['output']/'program.a816.json'
    image_path.write_text(json.dumps(program['image'],indent=2)+'\n')
    payload, labels = emit(program['output'], program['image'], program['build']['memory'],
                           program['labels'], probe=probe)
    program['xex'].write_bytes(payload)
    program['labels'].update(labels)
    program['build'].update(xex_sha256=sha256(program['xex']), loader_probe=probe,
                             image_sha256=sha256(image_path),
                             manifest_sha256=sha256(program['output']/'manifest.bin'))
    program['build']['generated_sha256'] = {name:sha256(program['output']/name)
                                            for name in program['build']['generated_sha256']}
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')


def load_to_start(bridge, program, poison=False, bounds=None):
    bridge.bp_clear_all(); bridge.boot(str(program['xex']))
    if poison:
        bridge.bp_set(program['labels']['loader_init'])
        run_to(bridge,program['labels']['loader_init'])
        require(bridge.memdump(program['labels']['loader_initialized'],1) == b'\0',
                'Missed first INITAD callback')
        c = program['build']['memory']['constants']
        bridge.memload(c['TABLE'],bytes([0xa5])*c['TABLE_BYTES'])
        far_write(bridge,0x10000,bytes([0x5a])*4096,program['output'])
        if bounds == 'bounds-low':
            bridge.memload(0x2e7,struct.pack('<H',(adapter.STATE+1)))
        elif bounds == 'bounds-top':
            program['test_memtop'] = bridge.memdump(0x2e5,2)
            bridge.memload(0x2e5,struct.pack('<H',0x8fff))
        bridge.bp_clear_all()
    run_to(bridge,program['labels']['loader_start'],frame_limit=1800)


def loader_case(bridge, toolchain, output, variant):
    program = build(toolchain,ROOT/'examples/preemptive.act',output,banked=True,preemptive=True)
    c = program['build']['memory']['constants']
    if variant == 'transfers':
        program['image']['segments'].append({'address':0x3fffd,'bytes':[7,9,11,13,15,17],
                                             'writable':True,'executable':False})
        program['image']['zero_fill'].append({'address':0x50000,'size':65536,'writable':True})
        changed_image(program,True)
        bridge.bp_clear_all();bridge.boot(str(program['xex']))
        bridge.bp_set(program['labels']['loader_init']);run_to(bridge,program['labels']['loader_init'])
        far_write(bridge,0x4fff0,bytes([0xa5])*(65536+32),output)
        far_write(bridge,0x3fff0,bytes([0xa5])*32,output)
        bridge.bp_clear_all();run_to(bridge,program['labels']['loader_start'],frame_limit=1800,timeout=60)
        require(far_read(bridge,0x50000,65536,output) == bytes(65536),'Full-bank zero-fill failed')
        require(far_read(bridge,0x4fff0,16,output) == bytes([0xa5])*16
                and far_read(bridge,0x60000,16,output) == bytes([0xa5])*16,
                'Full-bank zero-fill crossed a destination guard')
        require(far_read(bridge,0x3fff0,32,output) == bytes([0xa5])*13+bytes([7,9,11,13,15,17])+bytes([0xa5])*13,
                'Cross-bank copy or guards failed')
        require(bridge.memdump(c['WORK']+9,1)[0] > 64,'Real callback VBI probes did not execute')
        require(bridge.memdump(program['labels']['loader_error'],1) == b'\0','Loader failed')
        return {'build':program['build'],'zero_fill_bytes':65536,'cross_bank_copy':True,
                'destination_guards':'intact','callback_vbi_count':bridge.memdump(c['WORK']+9,1)[0]}
    if variant == 'adoption':
        result,_ = execute(bridge,program,expected_status=4,
                           before_run=lambda b:b.memload(c['TABLE']+4,b'\1'))
        require(result['gateway_calls'] == result['switches'] == result['os_calls'] == 0,
                'Failed adoption allowed task execution')
        require(bridge.memdump(c['ADOPTED'],2) == b'\0\0','Failed adoption was published')
        return {'build':program['build'],'runtime':result,'adopted':False}
    if variant == 'context':
        changed_image(program,True)
        segs = xex_segments(program['xex'].read_bytes())
        first = next(d for a,d in segs if a == c['STAGE'] and int.from_bytes(d[4:6],'little'))
        source = f'''.setcpu "65816"
.segment "CODE"
.export start,done,timer_hook,timer_chain
start:
    tsx
    stx $2109
    cli
    lda #$be
    xba
    lda #$a9
    ldx #$35
    ldy #$67
    sed
    sec
    jsr ${program['labels']['loader_init']:04x}
    php
    pha
    txa
    pha
    tya
    pha
    phb
    phd
    cld
    tsx
    txa
    clc
    adc #7
    sta $2108
    ldy #0
copy:
    lda $0101,x
    sta $2100,y
    inx
    iny
    cpy #7
    bne copy
    xba
    sta $2107
done:
    jmp done
timer_hook:
    inc $210a
timer_chain:
    jmp $ffff
'''
        labels = assemble_probe(output/'callback',source,0x4000)
        # Drive setup plus one COPY through an actual emulation-mode JSR.
        harness = [(a,d) for a,d in segs if a in (c['LOADER'],c['MANIFEST'])]
        harness += [(0x4000,(output/'callback/probe.bin').read_bytes()),(c['STAGE'],first),
                    (0x2e0,struct.pack('<H',labels['start']))]
        write_xex(program['xex'],harness)
        bridge.bp_clear_all();bridge.boot(str(program['xex']));run_to(bridge,labels['start'])
        bridge.memload(labels['timer_chain']+1,bridge.memdump(0x210,2))
        bridge.memload(0x210,struct.pack('<H',labels['timer_hook']))
        bridge.memload(0x210a,b'\0')
        for address,value in ((0xd208,0),(0xd200,0x80),(0xd201,0),(0xd209,0),(0x10,1),(0xd20e,1)):
            bridge.poke(address,value)
        bridge.bp_set(labels['done']);run_to(bridge,labels['done'])
        raw = bridge.memdump(0x2100,10)
        require(raw[:8] == bytes([0,0,0,0x67,0x35,0xa9,0x39,0xbe]) and raw[8]==raw[9],
                f'INITAD changed caller context: {raw.hex()}')
        require(bridge.memdump(c['WORK']+9,1) == b'\1','No actual VBI in callback')
        irq_count = bridge.memdump(0x210a,1)[0]
        require(irq_count > 0,'No actual timer IRQ in callback')
        return {'context':raw.hex(),'callback_vbi':True,'callback_irq_count':irq_count,
                'xex_sha256':sha256(program['xex'])}
    segs = xex_segments(program['xex'].read_bytes())
    # The first extent may be BSS now that ordinary globals live in upper RAM.
    # A ZERO record has only its eight-byte header, but still mutates the image.
    first = next(i for i,(a,d) in enumerate(segs)
                 if a == c['STAGE'] and int.from_bytes(d[4:6],'little'))
    expected_image = bytearray([0x5a])*4096
    expected_error = 3
    if variant in ('bounds-low','bounds-top'):
        expected_error = 1
    elif variant == 'manifest':
        i = next(i for i,(a,_) in enumerate(segs) if a == c['MANIFEST'])
        a,d = segs[i];d = bytearray(d);d[32+4] = 1;segs[i] = (a,bytes(d));expected_error = 2
    elif variant in ('missing','early'):
        segs = segs[:first if variant == 'early' else -3]
        segs.append((0x2e0,struct.pack('<H',program['labels']['loader_start'])))
        expected_error = 4
    elif variant == 'replay':
        # The original record is accepted before its replay is rejected.
        index, offset, count, kind, _ = struct.unpack('<HHHBB',segs[first][1][:8])
        descriptor = (output/'manifest.bin').read_bytes()[32+c['TABLE_BYTES']+index*8:]
        destination = int.from_bytes(descriptor[:3],'little')+offset
        payload = bytes(count) if kind == 1 else segs[first][1][8:]
        for i,value in enumerate(payload):
            if 0x10000 <= destination+i < 0x11000:
                expected_image[destination+i-0x10000] = value
        segs[first+2:first+2] = segs[first:first+2]
    elif variant == 'extra-callbacks':
        segs = [item for pair in ((item,(0x2e2,struct.pack('<H',program['labels']['loader_init'])))
                                  if item[0] == 0x2e2 else (item,) for item in segs) for item in pair]
        expected_error = 0
    else:
        a,d = segs[first];d = bytearray(d)
        offset = {'index':0,'offset':2,'count':5,'kind':6,'reserved':7}[variant]
        d[offset] = 255;segs[first] = (a,bytes(d))
    write_xex(program['xex'],segs)
    load_to_start(bridge,program,poison=True,bounds=variant)
    bridge.bp_set(program['labels']['loader_done'] if expected_error else program['labels']['start'])
    run_to(bridge,program['labels']['loader_done'] if expected_error else program['labels']['start'])
    error = bridge.memdump(program['labels']['loader_error'],1)[0]
    require(error == expected_error,f'Loader error {error}, expected {expected_error}')
    if variant == 'bounds-top':
        # Retire the injected bound only after terminal failure, so the CPU
        # inspection helper can use its known cold-launch scratch arena.
        bridge.memload(0x2e5,program['test_memtop'])
    if expected_error and expected_error != 1:
        require(bridge.memdump(c['ENTERED'],1) == b'\0','Failed image entered kernel')
    if expected_error in (1,2):
        require(bridge.memdump(c['TABLE'],c['TABLE_BYTES']) == bytes([0xa5])*c['TABLE_BYTES'],
                'Manifest failure published partial claims')
    if variant in ('index','offset','count','kind','reserved','manifest','early','replay','bounds-low','bounds-top'):
        require(far_read(bridge,0x10000,4096,output) == bytes(expected_image),'Rejected record wrote image bytes')
    return {'error':error,'initialized':bridge.memdump(program['labels']['loader_initialized'],1)[0],
            'xex_sha256':sha256(program['xex'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--case',help='Run one named case')
    args = parser.parse_args()
    toolchain = compiler(args.compiler_dir)
    bridge_dir,rom = args.bridge_dir.resolve(),args.rom.resolve()
    platform_files(bridge_dir,rom)
    output = ROOT/'build/banked-tests';output.mkdir(parents=True,exist_ok=True)
    cases = [('profile','profile',{})]
    for optimize in (False,True):
        mode = 'opt' if optimize else 'raw'
        for count in (2,16,256):
            cases.append((f'policy-{count}-{mode}','policy',{'count':count,'optimize':optimize}))
        cases.append((f'demo-{mode}','native',{'optimize':optimize}))
        cases.append((f'locks-{mode}','native',{'optimize':optimize,'fixture':'locks'}))
        cases.append((f'kernel-memory-{mode}','native',{'optimize':optimize,'fixture':'memory',
                                                     'kernel_init_name':'BANKEDMEMORY.KernelInit'}))
        for flags in (0xc9,0xd9,0xe9,0xf9,0xcd):
            cases.append((f'registers-{flags:02x}-{mode}','native',{'optimize':optimize,'probe_flags':flags}))
        for point in (9,10,16,18):
            cases.append((f'nmi-{point}-{mode}','native',{'optimize':optimize,'probe_nmi':point}))
        cases.append((f'timer-irq-{mode}','native',{'optimize':optimize,'timer_irq':True}))
    for variant in ('transfers','context','adoption','extra-callbacks','bounds-low','bounds-top','manifest','index','offset','count',
                    'kind','reserved','replay','early','missing'):
        cases.append((f'loader-{variant}','loader',{'variant':variant}))
    if args.case:
        cases = [c for c in cases if c[0] == args.case]
        require(cases,f'Unknown case: {args.case}')
    report = {'schema_version':1,'platform':PIN,'compiler_revision':toolchain['revision'],
              'inputs':{str(p.relative_to(ROOT)):sha256(p) for folder in ('tools','tests','tests/programs','abi','config','platform/altirraos','lib','toolchain')
                        for p in sorted((ROOT/folder).glob('**/*' if folder=='lib' else '*')) if p.is_file()},
              'status':'running','cases':[]}
    report_file = output/(f'{args.case}.json' if args.case else 'results.json')
    try:
        with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
            report['emulator_config'] = verify_machine(bridge,rom,PIN)
            for name,kind,options in cases:
                print(f'Running {name}...',flush=True)
                out = output/name
                if kind == 'profile':
                    observed = profile_probe(bridge,out)
                elif kind == 'policy':
                    observed = policy_probe(bridge,toolchain,out,**options)
                elif kind == 'loader':
                    observed = loader_case(bridge,toolchain,out,**options)
                else:
                    options = dict(options)
                    fixture = options.pop('fixture','demo')
                    timer_irq = options.pop('timer_irq',False)
                    source = ROOT/({'locks':'tests/programs/preemptive_locks.act',
                                    'memory':'tests/programs/banked_memory.act'}.get(fixture,'examples/preemptive.act'))
                    program = build(toolchain,source,out,banked=True,preemptive=True,**options)
                    result,screen = execute(bridge,program,timer_irq=timer_irq)
                    if fixture == 'memory':
                        require(data(bridge,program['image'],'acquired',True) == [2],'Kernel did not acquire bank 2')
                        require(data(bridge,program['image'],'progress') == [1,1],'Banked tasks stalled')
                        require(data(bridge,program['image'],'outputStatus',True) == [1,1],'OS output failed')
                        program_result = {'acquired':2,'progress':[1,1],'outputStatus':[1,1]}
                    else:
                        program_result = check_preemptive(bridge,program,fixture,result,screen)
                    observed = {'build':program['build'],'runtime':result,'program':program_result}
                    c = program['build']['memory']['constants']
                    seed = (out/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
                    require(bridge.memdump(c['TABLE'],len(seed)) == seed,'Task exit released image banks')
                    require(bridge.memdump(c['ADOPTED'],2) == b'\1\0','Kernel did not adopt table')
                    if timer_irq:
                        require(result['native_irq_count'] > 0,'No hardware IRQ observed')
                report['cases'].append({'name':name,'status':'pass','observed':observed})
        report['status'] = 'pass'
    except Exception as error:
        report['status'] = 'fail';report['error'] = str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} banked cases; report: {report_file}')


if __name__ == '__main__':
    main()
