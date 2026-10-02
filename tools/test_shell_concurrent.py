#!/usr/bin/env python3
"""Eight live Tasks: physical input/display, one DOS Read, memory/messages/signals."""
import adapter_state as adapter
from library_paths import read_source
import argparse,hashlib,json,os,shutil,time
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator,run_to
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
from test_shell_core import draw
from test_shell_commands import convert
from test_dos_stack import execute,ownership
from dos_concurrent_trace import call_marker,sector_end_marker
from generate_console import glyphs
from banked_test_memory import read as far_read

INPUT_PATHS=('tests/programs/shell_concurrent.act','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tools/test_shell_concurrent.py','lib/dos/doscooked.act','lib/dos/cookedline.act','tools/test_shell_core.py','tools/shell_concurrent_trace.py')
LOADED_INPUTS={name:sha256(ROOT/name)for name in INPUT_PATHS}

PROBE=dict(expected=0,verified=4,seed=8,phase=9,go=10,finish=11,collected=12,visible=14,duringRead=16,initialAlloc=18,finalAlloc=22)
MIX=dict(readyA=0,readyB=1,readyC=2,stopA=3,stopPeers=4,replies=5,destination=8,message=11,output=14,flood=17,floods=20,allocations=22,signals=26,messages=30)
LIMITS=dict(checkpoint_host_seconds=180,checkpoint_guest_frames=9000,completion_host_seconds=1800,completion_guest_frames=30000)

def marks_for(p):
    names=('native_nmi','native_irq','sio_start','sio_retire','sio_shutdown','sio_terminal','signal_post','sio_alarm','sio_watchdog','input_capture','input_notify','tasks_forbid','tasks_permit')
    marks={n:p['labels'][n] for n in names}
    for short,prefix in [('read_collected','M_SHELLEDITPROBE_READCOLLECTED_'),('echo_visible','M_SHELLEDITPROBE_EDITORWRITEOBSERVED_'),('allocation_cycle','M_CONSOLECONCURRENT_ALLOCATECYCLE_'),('display_quantum','M_CONSOLEDISPLAY_QUANTUM_'),('terminal_feed','M_CONSOLECORE_FEED_'),('command_begin','M_CONSOLECONCURRENT_COMMANDBEGIN_'),('command_end','M_CONSOLECONCURRENT_COMMANDEND_')]:
        values=[r['address'] for r in p['image']['routines'] if r['name'].startswith(prefix)];require(len(values)==1,'Ambiguous marker '+short);marks[short]=values[0]
    p['labels']['dos_read']=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_DOS_READ_'))
    marks['read_begin']=call_marker(p,'M_CONSOLECONCURRENT_READERTRANSFER_','dos_read')
    marks['read_end']=call_marker(p,'M_CONSOLECONCURRENT_READERTRANSFER_','dos_read',True)
    marks['sector_end']=sector_end_marker(p)
    # The worker enters this call only when finishing a nonempty READ. Actual
    # reply publication lies between here and the client's collected marker.
    marks['read_reply_begin']=call_marker(p,'M_CONSOLEDRIVER_READQUANTUM_','console_control')
    return marks

def execute_case(p,out,size,speed,trace,marks,schedule=None):
    out.mkdir(parents=True,exist_ok=True)
    for name in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):os.environ.pop(name,None)
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    media=out/'volume.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);media_hash=sha256(media)
    require(sha256(p['xex'])==p['build']['xex_sha256'],'Execution image changed')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','810' if speed else 'fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.mount(0,str(media))
        saved={};observations=[];actions=[];origin=None
        def symbol(name):return next(x for x in p['image']['data'] if '_CONSOLECONCURRENT_'+name+'_' in x['name'])
        q=symbol('PROBE');m=symbol('MIX');reader=symbol('READER')['address']
        require(q['size']==26 and m['size']==34 and symbol('READER')['size']==22,'Fixture record layout changed')
        q=q['address'];m=m['address'];cs=p['build']['memory']['console_storage'];ts=p['build']['task_storage'];instance=cs['INSTANCE']
        def readfar(at,n):return bytes(b.eval_expr(f'db(${at+i:x})') for i in range(n))
        def rendezvous(condition,point='native_nmi',long=False):
            b.bp_clear_all();address=p['labels'][point];b.bp_set(address,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs;last_report=time.monotonic()
            def regs():
                nonlocal last_report
                r=original();pc=int(r['PC'].lstrip('$'),16)
                if pc in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Concurrent console stopped before checkpoint')
                if time.monotonic()-last_report>30:
                    print('Concurrent progress: frame',b.eval_expr('@frame'),'serial completions',b.eval_expr(f'dw(${ts["BASE"]+0x838:x})'),flush=True)
                    last_report=time.monotonic()
                return r
            b.regs=regs
            try:run_to(b,address,LIMITS['completion_guest_frames' if long else 'checkpoint_guest_frames'],LIMITS['completion_host_seconds' if long else 'checkpoint_host_seconds'],condition)
            finally:b.regs=original
        def state(label):
            live=b.eval_expr(f'db(${ts["LIVE"]:x})');created=b.eval_expr(f'dw(${ts["CREATED"]:x})')
            contexts=[b.eval_expr(f'db(${ts["BASE"]+i*ts["SIZE"]+ts["TCB_STATE"]:x})') for i in range(8)]
            observations.append(dict(stage=label,frame=b.eval_expr('@frame'),live=live,created=created,contexts=contexts,floods=b.peek16(m+MIX['floods'])))
            require(live==8 and created==7 and all(contexts),'Eight simultaneous public Tasks not established')
        def input_action(key,state):
            require(b._cmd_ok(f'KEY {key} {state}')['raw_scan'],'Physical key injection required')
            actions.append(dict(key=key,state=state,frame=b.eval_expr('@frame')-origin))
        def before(b):
            nonlocal origin
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
            expected=777 if size==128 else 70003
            for i,v in enumerate(expected.to_bytes(4,'little')):b.poke(q+PROBE['expected']+i,v)
            b.poke(q+PROBE['seed'],83 if size==128 else 129)
            b._cmd_ok('KEY ALL up')
            if trace:b.profile_start()
            if schedule is None:
                rendezvous(f'db(${q+PROBE["phase"]:x})=1');state('admitted');origin=b.eval_expr('@frame')
                b.poke(q+PROBE['go'],1);actions.append(dict(go=1,frame=0))
                rendezvous(f'(db(${q+PROBE["phase"]:x})=2)&(db(${reader+4:x})=1)',long=True);state('large-read')
                sd=ts['BASE']+0x800
                rendezvous(f'(db(${sd+1:x})=11)&(dw(${sd+10:x})<8)',point='native_irq')
                for index,key in enumerate(('E','C','H','O','SPACE','O','K','SPACE','RETURN')):
                    if index:rendezvous(f'db(${cs["INSTANCE"]+51:x})=2')
                    input_action(key,'down')
                    rendezvous(f'dw(${q+PROBE["visible"]:x})={index+1}')
                    input_action(key,'up');rendezvous(f'@frame>={b.eval_expr("@frame")+4}')
                    print('Completed cooked echo',index+1,'of 9',flush=True)
            else:
                # The admitted checkpoint anchors guest time; host-loaded ROM boot
                # can begin a few video frames earlier on another cold boot.
                # Preserve exact frame intervals and the actual IRQ/NMI points.
                # The first key was injected at a serial IRQ rendezvous.
                for index,action in enumerate(schedule):
                    if 'go' in action:
                        require(index==0 and action['frame']==0,'Invalid replay origin')
                        rendezvous(f'db(${q+PROBE["phase"]:x})=1');state('admitted');origin=b.eval_expr('@frame')
                        b.poke(q+PROBE['go'],1);actions.append(dict(action));continue
                    if index==1:
                        rendezvous(f'(db(${q+PROBE["phase"]:x})=2)&(db(${reader+4:x})=1)',long=True);state('large-read')
                        sd=ts['BASE']+0x800;rendezvous(f'(db(${sd+1:x})=11)&(dw(${sd+10:x})<8)',point='native_irq')
                    else:rendezvous(f'@frame>={origin+action["frame"]}')
                    actual_frame=b.eval_expr('@frame')-origin
                    require(actual_frame==action['frame'],f'Replay input frame changed at action {index} {action}: got {actual_frame}')
                    input_action(action['key'],action['state'])
            rendezvous(f'db(${q+PROBE["phase"]:x})=3',long=True)
            rendezvous(f'dw(${instance+14:x})>=dw(${instance+16:x})')
            cells=int.from_bytes(readfar(instance,3),'little');retained=readfar(cells,960);physical=b.memdump(saved['at'],960)
            expected_screen=bytearray(glyphs()[v] for v in retained)
            cursor=b.eval_expr(f'dw(${instance+12:x})')*40+b.eval_expr(f'dw(${instance+10:x})');expected_screen[cursor]^=128
            require(physical==expected_screen,'Physical screen does not match retained cells/cursor')
            require(retained.count(35)>650,'Missing shared-writer scrolling')
            for name,raw in [('cells',retained),('screen',physical)]:(out/(name+'.bin')).write_bytes(raw)
            # Read the observer allocation while it is still owned. FreeMem
            # may put a free-list header over its first bytes during cleanup.
            storage=int.from_bytes(b.memdump(symbol('FIXTURESTORAGE')['address'],3),'little')
            captured=int.from_bytes(b.memdump(symbol('CAPTURECOUNT')['address'],4),'little')
            (out/'writes.bin').write_bytes(readfar(storage,captured))
            (out/'screen.png').write_bytes(b.screenshot())
            observations.append(dict(stage='finished-display',frame=b.eval_expr('@frame'),screen_sha256=sha256(out/'screen.bin'),cells_sha256=sha256(out/'cells.bin')))
            b.poke(q+PROBE['finish'],1);b.bp_clear_all()
        try:rt,_=execute(b,p,before_run=before,timeout=LIMITS['completion_host_seconds'],frame_limit=LIMITS['completion_guest_frames'])
        except Exception:
            sp=symbol('SHELL')['address'];sp=int.from_bytes(b.memdump(sp,3),'little')
            print('Shell pointer/state',hex(sp),[b.eval_expr(f'dw(${sp+i:x})')for i in (24,28,54)],'readerTask',b.memdump(symbol('READERTASK')['address'],61).hex(),flush=True)
            print('Native status',b.memdump(adapter.STATE,64).hex(),'probe',b.memdump(q,26).hex(),'mix',b.memdump(m,34).hex(),'reader',b.memdump(reader,22).hex(),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        if trace:b.profile_stop()
        require(b.peek(q+PROBE['phase'])==b'\4','Missing cleanup checkpoint')
        require(rt['created']==7 and rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Task/stack qualification failed')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Console ownership not restored')
        ownership(b,p,p['output']);hardware=far_read(b,ts['BASE']+0x800,128,p['output'])
        require(hardware[0]==hardware[1]==hardware[45]==0 and hardware[12:15]==hardware[16:19]==bytes(3),'Serial ownership/pointers retained')
        require(sha256(media)==media_hash,'Media changed')
        counters={name:int.from_bytes(b.memdump(q+PROBE[name],4 if name in ('expected','verified','initialAlloc','finalAlloc') else 2),'little') for name in ('expected','verified','collected','visible','duringRead','initialAlloc','finalAlloc')}
        counters.update({name:int.from_bytes(b.memdump(m+MIX[name],2 if name=='floods' else 4),'little') for name in ('floods','allocations','signals','messages')})
        counters.update({name:int.from_bytes(b.memdump(symbol(name.upper())['address'],4 if name=='captureCount'else 2),'little')for name in ('captureCount','commands','commandOverlap')})
        expected_writes=bytearray(draw(b''));line=bytearray()
        for ch in b'echo ok ':line.append(ch);expected_writes+=draw(line)
        expected_writes+=b'\nok\n'+draw(b'')
        expected_writes+=convert(bytes((i&255)^83 for i in range(777)))+b'SUB/\n'
        require(counters['captureCount']==len(expected_writes)and counters['commands']==5,'Missing command/editor output')
        actual=(out/'writes.bin').read_bytes()
        (out/'writes.bin').write_bytes(actual);(out/'expected.bin').write_bytes(expected_writes)
        require(actual==expected_writes,'Actual shell command/editor bytes differ')
        require(size!=256 or counters['commandOverlap']>0,'No shell command queued during complete Read')

    if trace:
        with (out/'emulator.log').open() as src,(out/'trace.log').open('w') as dst:
            for line in src:
                if '[SIOPOC] ' in line or '[SIOTXN] ' in line:dst.write(line)
    result=dict(status='pass',runtime=rt,machine=machine,sector_bytes=size,speed=speed,media_sha256=media_hash,counters=counters,observations=observations,schedule=actions,schedule_origin_frame=origin,schedule_clock='Video frames relative to the eight-Task admitted checkpoint; first key at the same serial IRQ phase, remaining keys at NMI',hardware=hardware.hex(),writes_sha256=sha256(out/'writes.bin'),expected_sha256=sha256(out/'expected.bin'),image_sha256=p['build']['image_sha256'],xex_sha256=sha256(p['xex']))
    (out/'case.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def run(out,mode,size,speed,bank,trace,toolchain=None):
    import generate_tasks,re
    out.mkdir(parents=True,exist_ok=True)
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned shell emulator')
    source=out/'shell_concurrent.act';source.write_bytes((ROOT/'tests/programs/shell_concurrent.act').read_bytes())
    core=(ROOT/'examples/shell/shell-session.inc').read_text()
    for name in ('shell-commands.inc','shell-redirection.inc'):core=core.replace('"'+name+'"','"'+str(ROOT/'examples/shell'/name)+'"')
    core=core.replace('USE EXEC\n','USE EXEC\nUSE SHELLEDITPROBE\n',1)
    core=core.replace('BYTE FUNC ShellOpen(BYTE POINTER consoleName)', 'BYTE FUNC ShellOpen(BYTE POINTER consoleName)\n  SHELLEDITPROBE.Bind(@captureCount,BYTE POINTER(@probe),@reader.active,fixtureStorage)')
    require(core.count('  LET written=DOS.Write(')==1,'Missing shell write observer')
    core=core.replace('  LET written=DOS.Write(', '  SHELLEDITPROBE.Capture(bytes,count)\n  LET written=DOS.Write(')
    core+='\nLONGCARD captureCount\n'
    (out/'shell-observed.inc').write_text(core)
    (out/'shelleditprobe.act').write_text('''MODULE SHELLEDITPROBE
USE HEAPCORE
LONGCARD POINTER total
BYTE POINTER probe,active,captureBuffer
PUBLIC PROC Bind(LONGCARD POINTER count BYTE POINTER state,reading,buffer)
  total=count probe=state active=reading captureBuffer=buffer
RETURN
PUBLIC PROC Capture(BYTE POINTER bytes CARD count)
  BYTE POINTER target
  CARD index
  IF total^+LONGCARD(count)>8192 THEN HEAPCORE.Abort($edf0) FI
  target=captureBuffer+SIZE(total^)
  IF count<>0 THEN FOR index=0 TO count-1 DO target(index)=bytes(index) OD FI
  total^==+LONGCARD(count)
RETURN
PUBLIC PROC ReadCollected(BYTE unused)
  CARD POINTER counter
  counter=CARD POINTER(ADDRESS(probe)+SIZE(12)) counter^==+1
  IF active^<>0 THEN counter=CARD POINTER(ADDRESS(probe)+SIZE(16)) counter^==+1 FI
RETURN
PUBLIC PROC EditorWriteObserved(BYTE unused)
  CARD POINTER counter
  counter=CARD POINTER(ADDRESS(probe)+SIZE(14)) counter^==+1
RETURN
ENDMODULE
''')
    cooked=read_source(ROOT/'lib/dos/doscooked.act').replace('USE EXEC','USE EXEC\nUSE SHELLEDITPROBE',1)
    cooked=cooked.replace('  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope)','  IF reading=0 THEN SHELLEDITPROBE.Capture(buffer,length) FI\n  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope)')
    cooked=cooked.replace('error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope)\n  secondary=LONGINT(error)','error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope) secondary=LONGINT(error)\n  IF reading<>0 THEN SHELLEDITPROBE.ReadCollected(0) FI')
    cooked=cooked.replace('        state.drawn=0\n      FI','        state.drawn=0\n      FI\n      SHELLEDITPROBE.EditorWriteObserved(0)')
    (out/'doscooked.act').write_text(cooked)
    if size==256:
        text=source.read_text().replace('BYTE ARRAY readPath=[68 65 84 65 46 66 73 78 0]','BYTE ARRAY readPath=[76 65 82 71 69 46 66 73 78 0]').replace('BYTE ARRAY readBase=[68 49 58 84 79 79 76 83 47 83 85 66 0]','BYTE ARRAY readBase=[68 49 58 0]');source.write_text(text)
    entries=('MAIN','READERENTRY','PRODUCERENTRY','SIGNALENTRY','RECEIVERENTRY')
    original=generate_tasks.task_entries
    def fixture_entries(image):
        selected=[r for r in image['routines']if any(r['name'].startswith('M_CONSOLECONCURRENT_'+name+'_')for name in entries)]
        require(len(selected)==5,'Missing fixture Task entry')
        return original(dict(image,routines=selected))
    generate_tasks.task_entries=fixture_entries
    try:p=build(toolchain if toolchain is not None else compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,
                system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size,profile=2 if speed else 1)])
    finally:generate_tasks.task_entries=original
    marks=marks_for(p)
    from dos_streams_timing import endpoint_marks
    marks.update(endpoint_marks(p))
    first=execute_case(p,out/('observed' if trace else 'functional'),size,speed,trace,marks)
    r=dict(status='pass',build=p['build'],source_inputs=LOADED_INPUTS,fixture_sha256=sha256(source),hook_sha256=sha256(out/'shell-observed.inc'),fixture_task_entries=entries,pin=PIN,marks=marks,limits=LIMITS,case=first)
    if trace:
        from shell_concurrent_trace import analyze
        r['timing']=analyze(out/'observed/trace.log',marks,out/'observed/volume.atr',size,speed,first['counters']['verified'])
        require(r['timing']['verdict']=='pass','Console concurrency timing failed: '+str(r['timing']['violations']))
        from dos_streams_timing import analyze as stream_timing
        r['stream_timing']=stream_timing(out/'observed/trace.log',marks)
        r['replay']=execute_case(p,out/'replay',size,speed,False,marks,first['schedule'])
        require(r['replay']['schedule']==first['schedule']and r['replay']['xex_sha256']==first['xex_sha256']and r['replay']['writes_sha256']==first['writes_sha256'],'Image/input/output changed in replay')
        require(r['replay']['observations'][-1]['screen_sha256']==first['observations'][-1]['screen_sha256'],'Replay screen changed')
    return r
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--sector-size',type=int,choices=(128,256),default=128);a.add_argument('--speed',type=int,choices=(0,1),default=0);a.add_argument('--bank',type=int,default=1);a.add_argument('--trace',action='store_true');a.add_argument('--output',type=Path,required=True);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(out,args.case,args.sector_size,args.speed,args.bank,args.trace,compiler(args.compiler_dir))
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Concurrent console passed',args.case,args.sector_size,args.speed,args.bank,flush=True)
