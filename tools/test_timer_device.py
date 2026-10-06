#!/usr/bin/env python3
"""Execute real VBI timer requests through the public device API."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, execute, verify_machine, require, read_build
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership

PIN=json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())


def lifecycle_program(toolchain,output,optimize,large=False):
    from native_program import command
    from test_banked import changed_image
    source=ROOT/'tests/programs/timer_lifecycle.act'
    if large:
        from library_paths import read_source
        output.mkdir(parents=True,exist_ok=True)
        text=read_source(source).replace('StackLower(1)','StackLower(6)').replace('StackUpper(1)','StackUpper(6)')
        source=output/'timer_lifecycle.act';source.write_text(text)
        (output/'heapapiprobe.act').write_bytes((ROOT/'tests/programs/heapapiprobe.act').read_bytes())
    program=build(toolchain,source,output,optimize=optimize,tasks=True,heap_probe=True,task_capacity=8)
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65','-I',output,'-I',ROOT/'platform/altirraos','-D',f'FAULT={program["labels"]["heap_fault"]}',
             '-o',output/'probe.o',ROOT/'tests/programs/timer_lifecycle.s'])
    command(['ld65','-C',output/'probe.cfg','-o',output/'probe.bin',output/'probe.o'])
    image=program['image']
    image['segments'].append(dict(address=0xe0000,bytes=list((output/'probe.bin').read_bytes()),writable=False,executable=True))
    at=program['labels']['heap_probe_fill']
    segment=next(s for s in image['segments'] if s['address']<=at<s['address']+len(s['bytes']))
    offset=at-segment['address'];segment['bytes'][offset:offset+4]=[0x5c,0,0,14]
    changed_image(program)
    program['checks_expected']=214
    return program


def snapshot_program(toolchain,output,optimize):
    from native_program import command
    from test_banked import changed_image
    output.mkdir(parents=True,exist_ok=True)
    program=build(toolchain,ROOT/'tests/programs/timer_snapshot.act',output,optimize=optimize,tasks=True,heap_probe=True)
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$0e0000,size=$1000,file=%O; } SEGMENTS { PROBE: load=RAM,type=ro; }\n')
    command(['ca65','-I',output,'-I',ROOT/'platform/altirraos','-D','HEAP_PROBE=1','-D','CONTROL=983040',
             '-o',output/'probe.o',ROOT/'tests/programs/timer_snapshot.s'])
    command(['ld65','-C',output/'probe.cfg','-o',output/'probe.bin','-Ln',output/'probe.lbl',output/'probe.o'])
    labels={line.split()[2].lstrip('.'):int(line.split()[1],16) for line in (output/'probe.lbl').read_text().splitlines()}
    image=program['image']; base=program['build']['memory']['timer_device_storage']['BASE']
    image['segments'] += [dict(address=0xe0000,bytes=list((output/'probe.bin').read_bytes()),writable=False,executable=True),
                          dict(address=0xf0000,bytes=[0]*16,writable=True,executable=False)]
    at=program['labels']['heap_probe_fill']
    segment=next(s for s in image['segments'] if s['address']<=at<s['address']+len(s['bytes']))
    offset=at-segment['address'];segment['bytes'][offset:offset+4]=[0x5c,*labels['arm'].to_bytes(3,'little')]
    start=program['labels']['timer_device_snapshot'];end=program['labels']['native_vbi_clock']
    segment=next(s for s in image['segments'] if s['address']<=start<s['address']+len(s['bytes']))
    raw=bytearray(segment['bytes']);low=start-segment['address'];high=end-segment['address']
    for i,offset in enumerate([0,2,4,6,10,None],1):
        original=bytes([0xa9,0,0,0x97,1]) if offset is None else bytes([0xaf,*(base+offset).to_bytes(3,'little'),0x97,1])
        require(raw[low:high].count(original)==1,'Snapshot instruction shape changed')
        at=raw.index(original,low,high)
        raw[at:at+len(original)]=bytes([0x22,*labels[f'snapshot_hook_{i}'].to_bytes(3,'little')]+[0xea]*(len(original)-4))
    segment['bytes']=list(raw);changed_image(program)
    program['checks_expected']=20
    return program


def clock_program(toolchain, output, optimize, rate):
    from library_paths import read_source
    output.mkdir(parents=True,exist_ok=True)
    ms=(0,1,16,17,19,20,999,1000,65535,0x80000000,0xffffffff)
    conversions=[(0,0,r,m) for r in (50,60) for m in ms]
    conversions += [(h,0xfffffff0,r,0xffffffff) for h in (7,0xffffffff) for r in (50,60)]
    conversions.append((4,5,0,1))
    relatives=[(h,l,s,u) for h,l in [(0,0),(7,0xfffffff0),(0xffffffff,0xfffffff0)]
               for s,u in [(0,0),(0,1),(0,999999),(1,0),(0xffff,999999),(0x10000,1),(0xffffffff,999999)]]
    relatives.append((0,0,1,1000000))
    expected=[rate];checks=4
    for h,l,r,m in conversions:
        deadline=(h<<32)+l+(m*r+999)//1000+1
        success=r in (50,60) and deadline<1<<64
        expected.extend([int(success),deadline>>32 if success else h,deadline&0xffffffff if success else l])
    for h,l,s,u in relatives:
        deadline=(h<<32)+l+s*rate+(u*rate+999999)//1000000+1
        error=4 if u>=1000000 else 2 if deadline>=1<<64 else 0
        expected.extend([error,0 if error else deadline>>32,0 if error else deadline&0xffffffff])
        if not error:checks+=1
    expected.extend([8,0,0,0xffffffff,0xffffffff,1])
    vectors=output/'timer-vectors.inc'
    vectors.write_text(f'CONST CONVERSION_COUNT={len(conversions)}, RELATIVE_COUNT={len(relatives)}, RESULT_WORDS={len(expected)}\n'+
        ''.join(f'LONGCARD ARRAY {name}=['+' '.join(f'${v:x}' for row in rows for v in row)+']\n'
                for name,rows in [('conversion',conversions),('relative',relatives)]))
    source=output/'timer_clock.act'
    source.write_text(read_source(ROOT/'tests/programs/timer_clock.act',{'timer-vectors.inc':vectors}))
    program=build(toolchain,source,output/'program',optimize=optimize,tasks=True)
    program.update(clock_expected=expected,checks_expected=checks)
    return program


def c_program(toolchain, output, optimize):
    from calypsi_build import emit
    from library_paths import read_source
    from generate_io import ABI as IO
    from generate_timer_device import ABI as TIMER
    output.mkdir(parents=True,exist_ok=True)
    records={'IORequest':IO['records']['IORequest'],**TIMER['records']}
    expressions=[]
    expected=[]
    for name,record in records.items():
        expressions.append(f'sizeof(struct {name})')
        expected.append((name+' size',record['size']))
        for field,_,offset in record['fields']:
            expressions.append(f'offsetof(struct {name},{field})')
            expected.append((name+' '+field,offset))
    probe=output/'timer-layout.c'
    probe.write_text('#include <devices/timer.h>\n__attribute__((section("exec_layout")))\n'+
                    'const UWORD TimerLayout[]={'+','.join(expressions)+'};\n')
    foreign=emit(output,[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/io.c',ROOT/'tests/programs/timer_device.c'],
                 [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/io.s',ROOT/'c/calypsi/image-info.s'],[],
                 optimize=optimize,roots=['ExecIOEntry','timer_checks'],probes=[(probe,expected)])
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{n.upper()}=${foreign["symbols"][n]:x}\n' for n in ('main','ExecIOEntry')))
    launcher=output/'timer-c.act'
    launcher.write_text('MODULE TIMERCPROBE\nUSE EXEC\nUSE HEAPCORE\n'+include.read_text()+
        read_source(ROOT/'c/calypsi/io-bridge.inc')+'''\nCARD FUNC POINTER cMain()
CARD result
PROC Main()
  BindIO()
  LET entry=ADDRESS POINTER(@cMain)
  entry^=C_MAIN
  result=cMain()
  IF result<>0 THEN HEAPCORE.Abort($fa00+result) FI
RETURN
ENDMODULE
''')
    program=build(toolchain,launcher,output/'program',optimize=optimize,tasks=True,foreign_image=foreign)
    program['c_checks']=foreign['symbols']['timer_checks']
    return program


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'build/interrupt-reply/ir5/timer')
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--from-build',type=Path)
    p.add_argument('--suite',choices=('basic','queue','binding','c','clock','snapshot','lifecycle'),default='basic')
    p.add_argument('--large-stack',action='store_true')
    p.add_argument('--video',choices=('PAL','NTSC'),default='PAL')
    args=p.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    pin=json.loads(json.dumps(PIN));pin['machine']['video']=args.video
    program=read_build(args.from_build) if args.from_build else lifecycle_program(
        compiler(args.compiler_dir),output/'lifecycle',args.mode=='opt',args.large_stack) if args.suite=='lifecycle' else snapshot_program(
        compiler(args.compiler_dir),output/'snapshot',args.mode=='opt') if args.suite=='snapshot' else clock_program(
        compiler(args.compiler_dir),output/'clock',args.mode=='opt',50 if args.video=='PAL' else 60) if args.suite=='clock' else c_program(
        compiler(args.compiler_dir),output/'c',args.mode=='opt') if args.suite=='c' else build(
        compiler(args.compiler_dir),ROOT/'tests/programs'/dict(basic='timer_device.act',
            queue='timer_queue.act',binding='timer_binding.act')[args.suite],output/'program',
        tasks=True,optimize=args.mode=='opt')
    report=dict(status='running',tier='development',qualification=False,build=program['build'])
    try:
        with emulator(ROOT/'build/altirra-irq-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=pin) as bridge:
            report['machine']=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',pin)
            try:
                report['runtime'],_=execute(bridge,program,timeout=120,frame_limit=3600)
            except Exception:
                names=('checks','openError','waitError') if args.suite=='basic' else ('result',) if args.suite=='c' else ('checks',)
                report['diagnostic']=dict(regs=bridge.regs(),observed={n:data(bridge,program['image'],n,True) for n in names},
                    timer=list(bridge.memdump(program['build']['memory']['timer_device_storage']['BASE'],32)),
                    native=list(bridge.memdump(program['build']['memory']['native_interrupt_storage']['BASE'],64)))
                raise
            report['checks']=(int.from_bytes(bridge.memdump(program['c_checks'],2),'little') if args.suite=='c'
                              else data(bridge,program['image'],'checks',True)[0])
            expected_checks=program.get('checks_expected',dict(basic=27,queue=70,binding=266,c=17).get(args.suite))
            if args.suite=='basic':
                report['concurrent_clock_reads']=data(bridge,program['image'],'concurrentReads',True)[0]
                require(0<report['concurrent_clock_reads']<128,'Missing bounded read/expiry overlap')
                expected_checks+=4+3*report['concurrent_clock_reads']
            require(report['checks']==expected_checks,
                    'Incomplete timer fixture: '+str(report['checks']))
            if args.suite=='clock':
                raw=bytes(data(bridge,program['image'],'results'))
                actual=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                require(actual==program['clock_expected'],'Clock/conversion mismatch: '+str([
                    (i,a,e) for i,(a,e) in enumerate(zip(actual,program['clock_expected'])) if a!=e]))
                report['clock_vectors']=dict(words=len(actual),actual=actual,expected=program['clock_expected'])
            if args.suite=='snapshot':
                require(bridge.memdump(0xf0000,4)==bytes([0,0,63,0]),'Missing real snapshot NMI checkpoints')
                require(report['runtime']['native_nmi_count']>=6,'Missing six raw clock writes')
                report['snapshot_interrupted_words']=6
            if args.suite=='lifecycle':
                report['clients']={name:data(bridge,program['image'],name,True)[0]
                                   for name in ('completed','aborted','expired')}
            clean_ownership(bridge,program,program['output'])
            from stack_budget import stack_usage
            report['stack_usage']=stack_usage(bridge,program['build']['memory'])
            state=bridge.memdump(program['build']['memory']['timer_device_storage']['BASE'],24)
            require(state[16:18]==bytes(2) and state[20:24]==bytes([0,0,255,0]),'Timer did not quiesce')
            require(bridge.memdump(program['build']['memory']['native_interrupt_storage']['BASE'],10)==bytes(10),
                    'Native source remained active after last Close')
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed timer device requests and cancellation')


if __name__=='__main__':
    main()
