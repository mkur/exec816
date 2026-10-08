#!/usr/bin/env python3
"""Focused emitted-code tests for native interrupt message publication."""
import argparse
import json
import re
from pathlib import Path

from native_program import ROOT, build, command, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator
from test_banked import changed_image
from test_cooperative import data
from test_heap_api import clean_ownership
from banked_test_memory import read as far_read
from stack_budget import stack_usage

PIN = json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())


def irq_case(bridge, toolchain, output, optimize, crossing=False, invalid=False):
    source=ROOT/'tests/programs/interrupt_reply.act'
    extents=[]
    if crossing:
        output.mkdir(parents=True,exist_ok=True)
        from library_paths import read_source
        text=read_source(source).replace('EXEC.MsgPort port','EXEC.MsgPort POINTER port').replace(
            'EXEC.Message item','EXEC.Message POINTER item')
        text=re.sub(r'@(port|item)\b(?!\.)',r'\1',text).replace(
            '  LET self=', '  port=EXEC.MsgPort POINTER($4fff3)\n  item=EXEC.Message POINTER($6fff4)\n  LET self=')
        source=output/'interrupt_reply.act'
        source.write_text(text)
        for helper in ('heapapiprobe.act','producerprobe.act'):
            (output/helper).write_text((ROOT/'tests/programs'/helper).read_text())
        extents=[(0x4fff0,bytes([0xa5])*64),(0x6fff0,bytes([0xa5])*48)]
    program = build(toolchain, source, output, image_data=extents,
                    optimize=optimize, tasks=True, heap_probe=True)
    labels = dict(CONTROL=0x0f0000, REPLY=program['labels']['exec_reply_msg_native'],
                  POST_CONTINUE=program['labels']['signal_post']+7,
                  FAULT=program['labels']['heap_fault'])
    if invalid:
        require(not crossing,'Select valid crossing or invalid contexts')
        labels.update(INVALID_NATIVE=1,PORT=next(d['address'] for d in program['image']['data'] if '_PORT_' in d['name']))
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65', '-I', output, '-I', ROOT/'platform/altirraos', *[v for k, a in labels.items() for v in ('-D', f'{k}={a}')],
             '-o', output/'probe.o', ROOT/'tests/programs/interrupt_reply.s'])
    command(['ld65', '-C', output/'probe.cfg', '-o', output/'probe.bin', '-Ln', output/'probe.lbl', output/'probe.o'])
    native = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
              for line in (output/'probe.lbl').read_text().splitlines()}
    image = program['image']
    image['segments'] += [dict(address=0x0e0000, bytes=list((output/'probe.bin').read_bytes()), writable=False, executable=True),
                          dict(address=labels['CONTROL'], bytes=[0]*32, writable=True, executable=False)]
    for symbol, destination in (('heap_probe_fill', 'arm'), ('signal_post', 'consumer')):
        address = program['labels'][symbol]
        segment = next(s for s in image['segments'] if s['address'] <= address < s['address']+len(s['bytes']))
        offset = address-segment['address']
        if symbol == 'signal_post':
            binding = program['build']['task_storage']['SERIAL_BINDING']-program['build']['task_storage']['BASE']
            require(segment['bytes'][offset:offset+7] == [0xa2, *binding.to_bytes(2, 'little'), 0xc2, 0x20, 0x0b, 0x3b],
                    'IRQ post prologue changed')
        segment['bytes'][offset:offset+4] = [0x5c, *native[destination].to_bytes(3, 'little')]
    changed_image(program)
    if invalid:
        results=[]
        for variant in range(9):
            runtime,_=execute(bridge,program,expected_status=4,timeout=180,
                before_run=lambda b:b.memload(labels['CONTROL']+30,bytes([variant])))
            port=bytes(data(bridge,image,'port'));message=bytes(data(bridge,image,'item'))
            require(port[16:25]==(labels['PORT']+19).to_bytes(3,'little')+bytes(3)+(labels['PORT']+16).to_bytes(3,'little'),
                    'Invalid native reply modified the queue')
            require(message[:6]==bytes(6) and message[6]==5,'Invalid native reply published a message')
            results.append(dict(variant=variant,runtime=runtime,queue_unchanged=True))
        return dict(build=program['build'],invalid_contexts=results)
    try:
        runtime, _ = execute(bridge, program, timeout=180, frame_limit=2400)
    except Exception:
        (output/'diagnostic.json').write_text(json.dumps(dict(
            regs=bridge.regs(), checks=data(bridge,image,'checks',True),
            control=list(far_read(bridge,labels['CONTROL'],32,output))),indent=2)+'\n')
        raise
    require(data(bridge, image, 'checks', True) == [11], 'IRQ reply fixture incomplete')
    control = far_read(bridge, labels['CONTROL'], 32, output)
    require(int.from_bytes(control[4:6], 'little') == 3, 'Missing native reply/context checks')
    require(runtime['native_irq_count'] >= 3, 'Missing hardware IRQ publication')
    clean_ownership(bridge, program, output)
    for base, payload in extents:
        raw=far_read(bridge,base,len(payload),output)
        start,end=(3,30) if base==0x4fff0 else (4,20)
        require(raw[:start]==payload[:start] and raw[end:]==payload[end:], 'Cross-bank record guard changed')
    return dict(build=program['build'], runtime=runtime, replies=3,
                stack_usage=stack_usage(bridge,program['build']['memory']),
                crossing=crossing,
                preserved=['A','X','Y','P','D','DBR','S'], native_probe_sha256=sha256(output/'probe.bin'))


def deferred_case(bridge, toolchain, output, boundary, idle=False, burst=1, resume_nmi=False,
                  switching=False):
    source=ROOT/'tests/programs/interrupt_deferred.act'
    if idle:
        output.mkdir(parents=True,exist_ok=True)
        from library_paths import read_source
        text=read_source(source).replace('  EXEC.Poll()\n','')
        source=output/'interrupt_deferred.act'
        source.write_text(text)
        (output/'heapapiprobe.act').write_text((ROOT/'tests/programs/heapapiprobe.act').read_text())
    program = build(toolchain, source, output,
                    optimize=True, tasks=True, heap_probe=True, probe_nmi=boundary)
    labels = dict(CONTROL=0x0f0000, REPLY=program['labels']['exec_reply_msg_native'],
                  FAULT=program['labels']['heap_fault'], HEAP_PROBE=1, BURST=burst)
    if resume_nmi:
        labels['RESUME_PROBE']=1
        if boundary==39:
            # Interrupt ordinary Task code, outside a COP's live guard, so
            # the quiet-return probe really must use its private trampoline.
            labels['QUIET_PROBE']=1
    if switching:
        require(boundary==39 and not idle and not resume_nmi,
                'Switching guard probe needs the root quiet-return boundary')
        labels['SWITCHING_PROBE']=1
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65', '-I', output, '-I', ROOT/'platform/altirraos',
             *[v for k, a in labels.items() for v in ('-D', f'{k}={a}')],
             '-o', output/'probe.o', ROOT/'tests/programs/interrupt_deferred.s'])
    command(['ld65', '-C', output/'probe.cfg', '-o', output/'probe.bin', '-Ln', output/'probe.lbl', output/'probe.o'])
    native = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
              for line in (output/'probe.lbl').read_text().splitlines()}
    image = program['image']
    image['segments'] += [dict(address=0x0e0000, bytes=list((output/'probe.bin').read_bytes()), writable=False, executable=True),
                          dict(address=labels['CONTROL'], bytes=[0]*64, writable=True, executable=False)]
    patches=[('heap_probe_fill', 'arm'), ('native_vbi_clock', 'raw_notify'),
             ('native_probe_work', 'complete')]
    if resume_nmi:
        patches.append(('native_resume_entry','before_resume'))
        start=program['labels']['native_resume_decode']
        end=program['labels']['native_return_intercept']
        segment=next(s for s in image['segments'] if s['address']<=start<s['address']+len(s['bytes']))
        offset=start-segment['address']
        body=bytes(segment['bytes'][offset:offset+end-start])
        original=program['labels']['native_resume_entry']+2
        replacement=native['resume_cop']+2
        # Preserve the production decoder; relocate only its exact private
        # COP PC/PBR comparisons to the diagnostic overlay's COP instruction.
        for old,new in ((original&0xffff,replacement&0xffff),(original>>16,replacement>>16)):
            needle=b'\xc9'+old.to_bytes(2,'little')
            require(body.count(needle)==1,'Private COP decoder comparison changed')
            body=body.replace(needle,b'\xc9'+new.to_bytes(2,'little'))
        segment['bytes'][offset:offset+len(body)]=list(body)
    for symbol, destination in patches:
        address = program['labels'][symbol]
        segment = next(s for s in image['segments'] if s['address'] <= address < s['address']+len(s['bytes']))
        offset = address-segment['address']
        segment['bytes'][offset:offset+4] = [0x5c, *native[destination].to_bytes(3, 'little')]
    changed_image(program)
    try:
        runtime, _ = execute(bridge, program, timeout=90, frame_limit=2400)
    except Exception:
        (output/'diagnostic.json').write_text(json.dumps(dict(
            regs=bridge.regs(), checks=data(bridge,image,'checks',True),
            control=list(far_read(bridge,labels['CONTROL'],32,output)),
            native=list(far_read(bridge,program['build']['memory']['native_interrupt_storage']['BASE'],64,output))),indent=2)+'\n')
        raise
    require(data(bridge, image, 'checks', True) == [8], 'Deferred fixture incomplete')
    control = far_read(bridge, labels['CONTROL'], 64, output)
    require(control[4:6] == bytes([1,1]), 'Missing notification or exactly-one reply')
    require(int.from_bytes(control[8:10],'little')==burst, 'Lost bounded callback work')
    require(list(control[16:16+burst])==[2-i%2 for i in range(burst)], 'Service budget was reset or exceeded')
    extra_ticks=int(resume_nmi)
    require(data(bridge,image,'atReturn',True) == [(int.from_bytes(control[6:8],'little')+extra_ticks)&0xffff],
            'Completion waited for a later tick')
    require(int.from_bytes(control[44:46],'little')==extra_ticks,'Missing private COP NMI handoff check')
    require(control[46]==int(switching),'Guarded adapter entry was not preserved')
    abi=json.loads((ROOT/'abi/native-interrupts.json').read_text())
    storage=program['build']['memory']['native_interrupt_storage']
    state=far_read(bridge,storage['BASE'],storage['BYTES'],output)
    first=abi['fields']['RESUME']+3
    stride=abi['resume_stride']
    count=program['build']['task_storage']['IDLE']+1
    require(not any(state[first:first+stride*count:stride]),'A Task or idle retained an armed return slot')
    clean_ownership(bridge, program, output)
    return dict(build=program['build'], runtime=runtime, boundary=boundary,
                stack_usage=stack_usage(bridge,program['build']['memory']),
                notifications=1, replies=1, subsequent_ticks=extra_ticks, idle=idle, callbacks=burst,
                resume_nmi=resume_nmi, switching_guard=switching, return_slots_clear=True,
                native_probe_sha256=sha256(output/'probe.bin'))


SOURCE_MODES=('reuse','edit-gate','callback-blocked','disabled','forbid','acknowledge')


def source_case(bridge, toolchain, output, mode):
    from library_paths import read_source
    output.mkdir(parents=True,exist_ok=True)
    source=output/'interrupt_source.act'
    source.write_text(read_source(ROOT/'tests/programs/interrupt_source.act').replace('CONST MODE=0',f'CONST MODE={mode}'))
    (output/'heapapiprobe.act').write_text((ROOT/'tests/programs/heapapiprobe.act').read_text())
    program=build(toolchain,source,output,optimize=True,tasks=True,heap_probe=True,probe_nmi=33)
    labels=dict(CONTROL=0x0f0000,REPLY=program['labels']['exec_reply_msg_native'],
                FAULT=program['labels']['heap_fault'],HEAP_PROBE=1,MODE=mode)
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65','-I',output,'-I',ROOT/'platform/altirraos',
             *[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],
             '-o',output/'probe.o',ROOT/'tests/programs/interrupt_source.s'])
    command(['ld65','-C',output/'probe.cfg','-o',output/'probe.bin','-Ln',output/'probe.lbl',output/'probe.o'])
    native={line.split()[2].lstrip('.'):int(line.split()[1],16) for line in (output/'probe.lbl').read_text().splitlines()}
    image=program['image']
    image['segments'] += [dict(address=0x0e0000,bytes=list((output/'probe.bin').read_bytes()),writable=False,executable=True),
                          dict(address=labels['CONTROL'],bytes=[0]*32,writable=True,executable=False)]
    for symbol,destination in (('heap_probe_fill','arm'),('native_vbi_clock','raw_notify'),('native_probe_work','complete')):
        address=program['labels'][symbol]
        segment=next(s for s in image['segments'] if s['address']<=address<s['address']+len(s['bytes']))
        offset=address-segment['address']
        segment['bytes'][offset:offset+4]=[0x5c,*native[destination].to_bytes(3,'little')]
    changed_image(program)
    try:
        runtime,_=execute(bridge,program,timeout=90,frame_limit=2400)
    except Exception:
        (output/'diagnostic.json').write_text(json.dumps(dict(regs=bridge.regs(),
            checks=data(bridge,image,'checks',True),control=list(bridge.memdump(labels['CONTROL'],32))),indent=2)+'\n')
        raise
    expected=13 if mode in (1,2,3) else 11 if mode==4 else 9
    require(data(bridge,image,'checks',True)==[expected],'Incomplete source lifecycle fixture')
    control=bridge.memdump(labels['CONTROL'],32)
    require(control[4]==2 and control[5]==(4 if mode==5 else 2),'Lost source generation or notification')
    require(control[8]==(2 if mode in (2,5) else 1),'Unexpected recursive/missing callback')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,mode=SOURCE_MODES[mode],
                stack_usage=stack_usage(bridge,program['build']['memory']),
                replies=2,notifications=control[5],activations=2,subsequent_ticks=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir', type=Path, required=True)
    p.add_argument('--bridge-dir', type=Path, default=ROOT/'build/altirra-irq-bridge')
    p.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output', type=Path, default=ROOT/'build/interrupt-reply/ir2')
    p.add_argument('--mode', choices=('raw','opt'), default='opt')
    p.add_argument('--suite', choices=('irq','invalid','deferred','sources'), default='irq')
    p.add_argument('--source-mode',choices=SOURCE_MODES,action='append')
    p.add_argument('--boundary', type=int, choices=range(30,40), action='append')
    p.add_argument('--idle', action='store_true')
    p.add_argument('--resume-nmi', action='store_true', help='Inject NMI before consuming the private return COP')
    p.add_argument('--switching', action='store_true', help='Hold the adapter switching guard across nested VBI return')
    p.add_argument('--burst', type=int, choices=(1,5), default=1)
    p.add_argument('--crossing', action='store_true')
    args = p.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    report = dict(status='running', tier='development', qualification=False, scope='Native IRQ ReplyMsg and register preservation', cases=[])
    try:
        with emulator(args.bridge_dir.resolve(), args.rom.resolve(), output, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, args.rom, PIN)
            if args.suite in ('irq','invalid'):
                report['cases'].append(irq_case(bridge, toolchain, output/('irq-'+args.mode), args.mode=='opt', args.crossing,args.suite=='invalid'))
            elif args.suite=='sources':
                report['scope']='Synthetic resident edit gates, source acknowledgement, disable, Forbid and reuse'
                for name in args.source_mode or SOURCE_MODES:
                    print('Source',name,flush=True)
                    report['cases'].append(source_case(bridge,toolchain,output/name,SOURCE_MODES.index(name)))
            else:
                report['scope'] = 'Deferred native reply at selected restore boundaries'
                for boundary in args.boundary or range(30,40):
                    print('Deferred boundary', boundary, flush=True)
                    report['cases'].append(deferred_case(bridge, toolchain, output/f'return-{boundary}', boundary, args.idle, args.burst,args.resume_nmi,args.switching))
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Passed', len(report['cases']), args.suite, 'cases')


if __name__ == '__main__':
    main()
