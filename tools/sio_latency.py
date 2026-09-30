#!/usr/bin/env python3
"""Disposable POKEY IRQ -> blocked worker -> SEROUT latency experiment."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct
import subprocess

from os_boundary import ROOT, PIN, emulator, require, run_to, sha256
from native_program import verify_machine

OUT = ROOT / 'build/sio-latency'
BASE_HZ = 1773447.5


def build(output, *, divisor=0, vbi=1, rom_irq=0, busy=1, stall=0, critical=0, phase=0, count=4096,
          source=None, extra_defines=None):
    output.mkdir(parents=True, exist_ok=True)
    defines = dict(DIVISOR=divisor, VBI=vbi, ROM_IRQ=rom_irq,
                   BUSY=busy, STALL=stall, CRITICAL=critical, PHASE=phase, BYTE_COUNT=count)
    defines.update(extra_defines or {})
    source = source or ROOT/'probes/sio-latency/probe.s'
    subprocess.run(['ca65', '-I', str(ROOT/'platform/altirraos'),
                    *[a for k,v in defines.items() for a in ('-D',f'{k}={v}')],
                    '-l', str(output/'probe.lst'), '-o', str(output/'probe.o'),
                    str(source)], check=True, timeout=30)
    subprocess.run(['ld65','-C',str(ROOT/'probes/sio-latency/probe.cfg'),
                    '-o',str(output/'probe.bin'),'-Ln',str(output/'probe.lbl'),
                    str(output/'probe.o')],check=True,timeout=30)
    labels = {label.lstrip('.'):int(addr,16) for _,addr,label in
              (line.split() for line in (output/'probe.lbl').read_text().splitlines())}
    payload = (output/'probe.bin').read_bytes()
    xex = output/'probe.xex'
    xex.write_bytes(struct.pack('<HHH',0xffff,0x3000,0x3000+len(payload)-1)+payload+
                    struct.pack('<HHH',0x2e0,0x2e1,labels['start']))
    return dict(output=output, labels=labels, xex=xex, defines=defines, source=source,
                xex_sha256=sha256(xex))


def execute(program, bridge_dir, rom, trace=False, shadow_rom=False,
            before_run=None, after_run=None):
    pin = copy.deepcopy(PIN)
    pin['machine']['clock_multiplier'] = 8
    pin['machine']['shadow_rom'] = shadow_rom
    output,labels = program['output'],program['labels']
    marker_names = ['stream_start','native_irq','native_nmi','irq_post','emulation_post',
                    'wait_call','wait_blocked','worker_wake','nmi_return','done']
    env_keys = ['EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS']
    old_env = {k:os.environ.get(k) for k in env_keys}
    if trace:
        os.environ['EXEC816_LATENCY_TRACE'] = '1'
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{labels[n]:x}' for n in marker_names)
    try:
        with emulator(bridge_dir,rom,output_dir=output,pin=pin) as bridge:
            bridge.config('siopatch','off')
            bridge.config('burstio','false')
            bridge.config('randdelay','false')
            bridge.boot(str(program['xex']))
            run_to(bridge,labels['start'],frame_limit=1800,timeout=60)
            machine = verify_machine(bridge,rom,pin)
            require(machine['siopatch']=='off' and not machine['burstio'] and
                    not machine['randdelay'],'SIO acceleration or random launch delay enabled')
            if trace:
                active=bridge.regs()
                require(active.get('clock_multiplier')==8 and
                        active.get('shadow_rom')==shadow_rom,'Incorrect active CPU/ROM speed')
            if before_run:
                before_run(bridge, program)
            vectors = bridge.memdump(0x256,9)
            vbi_vector = bridge.memdump(0x222,2)
            ser_vector = bridge.memdump(0x20c,2)
            old_critic = bridge.memdump(0x42,1)
            clock_before=int.from_bytes(bridge.memdump(0x12,3),'big')
            timer1_before=bridge.peek16(0x218)
            if trace:
                bridge.profile_start()  # Enables the existing CPU history path.
            bridge.bp_clear_all()
            bridge.bp_set(labels['done'])
            try:
                run_to(bridge,labels['done'],frame_limit=3600,timeout=120)
            except Exception:
                (output/'failure.json').write_text(json.dumps(dict(regs=bridge.regs(),
                    state=bridge.memdump(0x2000,256).hex(),pokey=bridge.pokey(),
                    history=bridge.history(256)),indent=2)+'\n')
                raise
            raw=bridge.memdump(0x2000,256)
            (output/'state.bin').write_bytes(raw)
            values=struct.unpack_from('<8H',raw)
            result=dict(zip(['status','sent','posts','waits','vbis','background_progress',
                             'worker_saved_s','background_saved_s'],values))
            require(result['status']==0x600d,f'Probe fault: {result}')
            require(result['sent']==result['posts']==result['waits']==program['defines']['BYTE_COUNT'],
                    f'Lost or duplicate wake/byte: {result}')
            require(bridge.memdump(0x256,9)==vectors and bridge.memdump(0x222,2)==vbi_vector
                    and bridge.memdump(0x20c,2)==ser_vector,'Vectors not restored')
            require(bridge.memdump(0x42,1)==old_critic,'CRITIC not restored')
            for address,length in [(0x100,16),(0x21f0,288),(0x23f0,288),
                                   (0x41f0,16),(0x4800,16),(0x49f0,16),(0x5000,16)]:
                require(bridge.memdump(address,length)==bytes([0xa5])*length,
                        f'Stack/DP guard corrupted at {address:04x}')
            require(not program['defines']['VBI'] or result['vbis']>0,'No VBI interference')
            result.update(machine=machine,regs=bridge.regs(),guards='pass',vectors='restored')
            result['antic']=bridge.antic()
            result.update(clock_before=clock_before,
                clock_after=int.from_bytes(bridge.memdump(0x12,3),'big'),timer1_before=timer1_before)
            if after_run:
                after_run(bridge, program, result)
    finally:
        for key,value in old_env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
    result.update(defines=program['defines'],xex_sha256=program['xex_sha256'],
                  rom_sha256=sha256(rom),emulator_sha256=sha256(bridge_dir/'AltirraBridgeServer'),
                  clock_multiplier=8,base_hz=BASE_HZ,cpu_nominal_hz=BASE_HZ*8,
                  shadow_rom=shadow_rom,resolved_machine=pin['machine'],
                  instrumented=trace)
    result['source_sha256']={str(p.relative_to(ROOT)):sha256(p) for p in
                            [program['source'],ROOT/'probes/sio-latency/probe.cfg',
                             *program.get('source_inputs', [])]}
    if trace:
        result['trace']=analyze(output/'emulator.log',labels,program['defines'])
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def analyze(path,labels,defines):
    events=[]
    for line in path.read_text().splitlines():
        if '[SIOPOC] ' in line:
            fields=line.split('[SIOPOC] ',1)[1].split()
            events.append(fields)
    require(events,'No passive timing trace')
    cpu=[e for e in events if e[0]=='cpu']
    require(all(int(e[3])==8 for e in cpu),'Active CPU multiplier is not 8')
    at=lambda e,name:e[0]=='cpu' and int(e[4],16)==labels[name]
    # POKEY supplies 64-bit scheduler time; CPU history exposes its low 32 bits.
    # Fresh boots start near a wrap, so extend CPU timestamps against nearby
    # hardware observations before doing any subtraction.
    tick=0
    for e in events:
        value=int(e[1])
        if e[0]=='cpu':
            value += round((tick-value)/(1<<32))*(1<<32)
            e[1]=str(value)
        tick=value
    start=next(i for i,e in enumerate(events) if at(e,'stream_start'))
    events=events[start:]
    ready=[e for e in events if e[0]=='ready']
    writes=[e for e in events if e[0]=='write']
    require(len(ready)==len(writes)==defines['BYTE_COUNT'],'Unexpected serial trace counts')
    require(all(int(e[3])==2*(defines['DIVISOR']+7) for e in ready),'Wrong serial period')
    require([int(e[2]) for e in ready]==[i&255 for i in range(defines['BYTE_COUNT'])],
            'Transmitted byte sequence differs from worker sequence')
    require(all(int(e[4])==0 for e in writes),'SEROUT overwritten before shifter load')
    require(all(int(e[4])&0x10 for e in ready),'Serial ready IRQ disabled during the stream')
    refills=[int(w[1])-int(r[1]) for r,w in zip(ready,writes[1:])]
    period=20*(defines['DIVISOR']+7)
    gaps=[int(b[1])-int(a[1])-period for a,b in zip(ready,ready[1:])]
    require(min(gaps)>=0,'Serial clock ran faster than the configured byte period')
    idle=[e for e in events if e[0]=='idle']
    require(len(idle)==1+sum(t>0 for t in gaps) and
            int(idle[-1][1])==int(ready[-1][1])+period,'Incomplete final byte or unaccounted underrun')
    waits=[]; wakes=[]; irqs=[]; posts=[]; pending_ready=None; entry=None; post=None
    for e in events:
        if at(e,'wait_call'): waits.append(e)
        if e[0]=='ready': pending_ready=int(e[1]); entry=None; post=None
        if at(e,'native_irq') and pending_ready is not None and entry is None:
            entry=int(e[1])+int(e[2])/int(e[3])
        if (at(e,'irq_post') and not defines['ROM_IRQ']) or at(e,'emulation_post'):
            post=int(e[1])+int(e[2])/int(e[3])
        if at(e,'worker_wake'):
            require(waits,'Wake without a Wait')
            wait=waits.pop(0)
            require(e[5:]==wait[5:],f'Native context changed across Wait: {wait} -> {e}')
            t=int(e[1])+int(e[2])/int(e[3])
            require(pending_ready is not None,'Wake without POKEY ready')
            wakes.append(t-pending_ready)
            if entry is not None: irqs.append(t-entry)
            if post is not None: posts.append(t-post)
    require(len(wakes)==defines['BYTE_COUNT'] and not waits,'Incomplete Wait/wake trace')
    def stats(xs):
        ordered=sorted(xs)
        return dict(count=len(xs),min_us=min(xs)/BASE_HZ*1e6,
            mean_us=sum(xs)/len(xs)/BASE_HZ*1e6,
            p99_us=ordered[(99*len(xs)-1)//100]/BASE_HZ*1e6,
            max_us=max(xs)/BASE_HZ*1e6)
    # Store every refill's two hardware timestamps independently of CPU markers.
    csv=['byte,ready_tick,refill_tick,latency_base_cycles,deadline_base_cycles,gap_after_byte_cycles']
    for i,(r,w,latency,gap) in enumerate(zip(ready,writes[1:],refills,gaps)):
        csv.append(f'{i},{r[1]},{w[1]},{latency},{period},{gap}')
    path.with_name('refills.csv').write_text('\n'.join(csv)+'\n')
    worst=max(range(len(refills)),key=refills.__getitem__)
    first,last=int(ready[worst][1]),int(writes[worst+1][1])
    names={v:k for k,v in labels.items()}
    window=[]
    for e in events:
        t=int(e[1])+(int(e[2])/int(e[3]) if e[0]=='cpu' else 0)
        if first<=t<=last:
            window.append(dict(base_tick=t,event=names.get(int(e[4],16),'cpu')
                               if e[0]=='cpu' else e[0]))
    return dict(actual_baud=BASE_HZ/(period/10),byte_deadline_us=period/BASE_HZ*1e6,
        stream_duration_us=(int(ready[-1][1])+period-int(ready[0][1]))/BASE_HZ*1e6,
        blocked_waits=sum(at(e,'wait_blocked') for e in events),
        ready_to_refill=stats(refills),ready_to_wake=stats(wakes),
        native_irq_entry_to_wake=stats(irqs) if irqs else None,
        post_entry_to_wake=stats(posts) if posts else None,
        deadline_misses=sum(t>=period for t in refills),gap_count=sum(t>0 for t in gaps),
        max_gap_us=max(gaps)/BASE_HZ*1e6,context_restoration='pass',
        worst_refill_byte=worst,worst_refill_window=window,
        log_sha256=sha256(path),refills_csv_sha256=sha256(path.with_name('refills.csv')),
        verdict='pass' if max(refills)<period and max(gaps)==0 else 'fail')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--trace',action='store_true')
    parser.add_argument('--matrix',action='store_true',help='Run the fixed decision matrix and pinned replay')
    parser.add_argument('--pinned-bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--divisor',type=int,default=0)
    parser.add_argument('--vbi',type=int,choices=[0,1],default=1)
    parser.add_argument('--rom-irq',type=int,choices=[0,1],default=0)
    parser.add_argument('--busy',type=int,choices=[0,1],default=1)
    parser.add_argument('--stall',type=int,default=0)
    parser.add_argument('--critical',type=int,choices=[0,1],default=0)
    parser.add_argument('--shadow-rom',action='store_true')
    parser.add_argument('--phase',type=int,default=0,help='Initial phase offset in groups of four NOPs')
    parser.add_argument('--count',type=int,default=4096)
    args=parser.parse_args()
    require(2<=args.count<=65535 and 0<=args.divisor<=255 and 0<=args.stall<=2000
            and 0<=args.phase<=127,'Invalid byte count, divisor, stall or phase')
    require(sha256(args.rom)==PIN['rom']['sha256'],'Unpinned ROM')
    if not args.trace:
        require(sha256(args.bridge_dir/'AltirraBridgeServer')==PIN['emulator']['sha256'],
                'Unpinned emulator; observational build requires --trace')
    output=(args.output or OUT/('matrix' if args.matrix else 'smoke')).resolve()
    if args.matrix:
        require(args.trace,'The decision matrix requires the observational build and --trace')
        require(sha256(args.pinned_bridge_dir/'AltirraBridgeServer')==PIN['emulator']['sha256'],
                'Incorrect unchanged emulator for replay')
        cases=[('native_no_vbi',dict(vbi=0),False),
               ('native_rom_vbi',{},False),
               ('rom_irq_rom_vbi',dict(rom_irq=1),False),
               ('native_critic',dict(critical=1),False),
               ('native_shadow',{},True),
               ('rom_irq_critic_shadow',dict(rom_irq=1,critical=1),True),
               ('candidate_long',dict(critical=1,count=65535),True),
               ('candidate_idle',dict(critical=1,busy=0,count=16384),True),
               *[(f'candidate_phase_{p}',dict(critical=1,phase=p),True) for p in (3,7,13)],
               ('negative_stall',dict(vbi=0,stall=1600,count=256),True)]
        output.mkdir(parents=True,exist_ok=True)
        report=dict(schema_version=1,created_utc=datetime.now(timezone.utc).isoformat(),
            target_baud=125000,platform_base=PIN,observer_patch_sha256=sha256(ROOT/'probes/sio-latency/observer.patch'),
            assembler=subprocess.check_output(['ca65','--version'],stderr=subprocess.STDOUT,text=True).strip(),
            cases=[])
        try:
            for name,options,shadow in cases:
                program=build(output/name,**options)
                result=execute(program,args.bridge_dir.resolve(),args.rom.resolve(),True,shadow)
                report['cases'].append(dict(name=name,**result))
                timing=result['trace']
                print(f"{name}: {timing['verdict']}; max {timing['ready_to_refill']['max_us']:.3f} us; "
                      f"{timing['deadline_misses']} misses / {result['sent']-1} refills",flush=True)
                if name.startswith('candidate_'):
                    require(timing['verdict']=='pass',f'Candidate fails: {name}')
                if name in ('native_rom_vbi','negative_stall'):
                    require(timing['verdict']=='fail',f'Expected deadline failure was not detected: {name}')
            replay=build(output/'pinned_replay',critical=1,count=65535)
            result=execute(replay,args.pinned_bridge_dir.resolve(),args.rom.resolve(),False,True)
            candidate=next(c for c in report['cases'] if c['name']=='candidate_long')
            require(result['xex_sha256']==candidate['xex_sha256'],'Replay image differs')
            for key in ['sent','posts','waits','vbis','clock_before','clock_after','background_progress',
                        'worker_saved_s','background_saved_s']:
                require(result[key]==candidate[key],f'Observation changed execution: {key}')
            report['cases'].append(dict(name='pinned_replay',**result))
            report['status']='candidate_passes_with_explicit_platform_constraints'
            print('pinned_replay: identical image, counters, clocks and saved contexts',flush=True)
        except Exception as error:
            report.update(status='error',error=str(error))
            raise
        finally:
            (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        return
    program=build(output,divisor=args.divisor,vbi=args.vbi,rom_irq=args.rom_irq,
                  busy=args.busy,stall=args.stall,critical=args.critical,phase=args.phase,count=args.count)
    result=execute(program,args.bridge_dir.resolve(),args.rom.resolve(),args.trace,args.shadow_rom)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
