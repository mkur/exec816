#!/usr/bin/env python3
"""Shared resident shell: real POKEY keys, exact writes, retained/physical screen."""
import adapter_state as adapter
from library_paths import read_source
import argparse,json,shutil,time,re
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine,read_build
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import terminal
from console_model import read_cells
from generate_program import fault_messages

def diagnostic_text(code, header):
    message=fault_messages().get(code)
    return (f"{header}: {message} ({code})\n" if message else f"{header}: Error code {code}\n").encode()
from os_boundary import emulator,run_to
from banked_test_memory import read as far_read
PIN=json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())
LIMITS=dict(checkpoint_host_seconds=240,checkpoint_guest_frames=12000,completion_host_seconds=1800,completion_guest_frames=60000)
HOOK='''
LONGCARD captureCount
CARD consumed,commandCount
BYTE suspend
PROC ShellWrite(DOS.FileHandle POINTER handle BYTE POINTER bytes CARD count)
  SHELLEDITPROBE.Capture(bytes,count)
  NativeShellWrite(handle,bytes,count)
RETURN
LONGINT FUNC ShellFinish()
  LONGINT result
  result=NativeShellFinish()
  IF shell=ShellState POINTER(0) THEN SHELLEDITPROBE.Release(0) FI
RETURN(result)
'''

from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def cooked_observer(out):
    """Observe real cooked transfers; never replace input, echo, or collection."""
    (out/'shelleditprobe.act').write_text('''MODULE SHELLEDITPROBE
USE EXEC
USE HEAPCORE
LONGCARD POINTER total
CARD POINTER keys
BYTE POINTER pause,probeStage,probeGate
PUBLIC BYTE POINTER captureBuffer
PUBLIC BYTE ready,releaseGate
PUBLIC PROC Bind(LONGCARD POINTER count CARD POINTER consumed BYTE POINTER suspend,phase,go)
  total=count keys=consumed pause=suspend probeStage=phase probeGate=go
  captureBuffer=EXEC.AllocMem(81920,EXEC.MEMF_UPPER OR EXEC.MEMF_LINEAR)
  IF captureBuffer=BYTE POINTER(0) THEN HEAPCORE.Abort($e5f1) FI
RETURN
PUBLIC PROC Capture(BYTE POINTER bytes CARD count)
  BYTE POINTER target
  CARD index
  IF total=LONGCARD POINTER(0) THEN RETURN FI
  IF total^+LONGCARD(count)>81920 THEN HEAPCORE.Abort($e5f0) FI
  target=captureBuffer+SIZE(total^)
  IF count<>0 THEN FOR index=0 TO count-1 DO target(index)=bytes(index) OD FI
  total^==+LONGCARD(count)
RETURN
PUBLIC PROC Release(BYTE unused)
  ready=1
  WHILE releaseGate=0 DO EXEC.Yield() OD
  EXEC.FreeMem(captureBuffer,81920) captureBuffer=BYTE POINTER(0) ready=0
RETURN
PUBLIC PROC Key(BYTE unused)
  keys^==+1
  IF pause^<>0 THEN
    pause^=0 probeStage^=4 probeGate^=0
    WHILE probeGate^=0 DO EXEC.Yield() OD
  FI
RETURN
ENDMODULE
''')
    s=read_source(ROOT/'lib/dos/doscooked.act').replace('USE EXEC','USE EXEC\nUSE SHELLEDITPROBE',1)
    s=s.replace('  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope)','  IF reading=0 THEN SHELLEDITPROBE.Capture(buffer,length) FI\n  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope)')
    s=s.replace('        state.drawn=0\n      FI','        state.drawn=0\n      FI\n      SHELLEDITPROBE.Key(0)')
    (out/'doscooked.act').write_text(s)

def instrument(out,source='shell_core.act'):
    cooked_observer(out)
    s=(ROOT/'examples/shell/shell-session.inc').read_text().replace('USE EXEC\n','USE EXEC\nUSE SHELLEDITPROBE\n',1).replace('PROC ShellWrite(','PROC NativeShellWrite(').replace('LONGINT FUNC ShellFinish()', 'LONGINT FUNC NativeShellFinish()')
    for name in ('shell-jobs.inc','shell-commands.inc','shell-redirection.inc','shell-path.inc'):
        s=s.replace('"'+name+'"','"'+str(ROOT/'examples/shell'/name)+'"')
    s=s.replace('BYTE FUNC ShellOpen(BYTE POINTER consoleName)','BYTE FUNC ShellOpen(BYTE POINTER consoleName)\n  SHELLEDITPROBE.Bind(@captureCount,@consumed,@suspend,@stage,@gate)')
    command_step='      ShellCommand()\n      ShellClear()'
    require(s.count(command_step)==1,'Missing shell command checkpoint')
    s=s.replace(command_step,'      ShellCommand()\n      commandCount==+1\n      ShellClear()')
    (out/'shell-observed.inc').write_text(s+HOOK)
    text=(ROOT/'tests/programs'/source).read_text().replace('../../examples/shell/shell-session.inc','shell-observed.inc')
    (out/source).write_text(text)
    return out/source

def collect_capture(b,p,out):
    """Snapshot the bounded heap observer before guest FreeMem reuses it.

    This rendezvous is after shell cleanup and is never latency evidence.
    Debugger reads preserve the paused native context (no far-copy trampoline).
    """
    def symbol(name):return next(d['address'] for d in p['image']['data'] if '_SHELLEDITPROBE_'+name.upper()+'_' in d['name'])
    total=next(d['address'] for d in p['image']['data'] if '_SHELLAPP_CAPTURECOUNT_' in d['name'])
    marker=p['labels']['native_nmi'];condition=f'db(${symbol("ready"):x})=1'
    b.bp_clear_all();b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
    original=b.regs
    def regs():
        r=original()
        if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Shell stopped before observer retirement')
        return r
    b.regs=regs
    try:run_to(b,marker,60000,1800,condition)
    finally:b.regs=original
    address=int.from_bytes(b.memdump(symbol('captureBuffer'),3),'little');count=int.from_bytes(b.memdump(total,4),'little')
    require(address>=65536 and count<=81920,'Invalid observer allocation')
    result=bytearray()
    for at in range(address,address+count,2):result.extend((b.eval_expr(f'dw(${at:x})')&65535).to_bytes(2,'little'))
    (out/'writes.bin').write_bytes(result[:count])
    b.poke(symbol('releaseGate'),1);b.bp_clear_all()
    return address

def draw(line,old=None):
    if not line and old is None:return b'> '
    if old is None:old=line[:-1]
    if old and len(line)<=36 and len(line)>len(old) and line.startswith(old):
        return bytes(line[len(old):])
    drawn=1+min(36,len(old)) if old else 0
    tail=line[-36:];shown=(b'<' if len(line)>36 else b' ')+tail
    extra=max(0,drawn-len(shown))
    return b'\b'*drawn+shown+b' '*extra+b'\b'*extra

KEYS={c:(c.upper(),False)for c in 'abcdefghijklmnopqrstuvwxyz0123456789'}
KEYS.update({c:(c,True)for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'})
KEYS.update({' ':('SPACE',False),'\n':('RETURN',False),'\t':('TAB',False),'\b':('BACKSPACE',False),':':('SEMICOLON',True),'"':('2',True),'*':('ASTERISK',False),'<':('LESS',False),'>':('GREATER',False),'/':('SLASH',False),'.':('PERIOD',False),';':('SEMICOLON',False),'|':('EQUALS',True),'-':('MINUS',False),'=':('EQUALS',False),'?':('SLASH',True)})

def run(t,out,mode,bank=1,size=128,no_mount=False,smoke=False,eof=None,external=None,reuse=False,pin=None,bridge_build=None,history_unavailable=False):
    pin = pin or PIN
    bridge_build = bridge_build or ROOT/'build/shell-console-bridge'
    out.mkdir(parents=True,exist_ok=True)
    source=instrument(out)
    if history_unavailable:
        # Real allocator exhaustion is covered by test_dos_cooked. Inject its
        # result here to check that the shell gives up once, preserving editing.
        cooked=read_source(ROOT/'lib/dos/cookedline.act')
        signature='PUBLIC LONGINT FUNC SetHistory(Session POINTER state BYTE enabled)'
        require(cooked.count(signature)==1,'Missing history fault checkpoint')
        cooked=cooked.replace(signature, 'PUBLIC CARD enableAttempts\n'+signature+'''

  IF enabled<>0 THEN
    enableAttempts==+1
    RETURN(ERROR_NO_FREE_STORE)
  FI
''')
        (out/'cookedline.act').write_text(cooked)
    if external:external.instrument(out)
    memory_profile=getattr(external,'memory_profile',None)
    if memory_profile is None:
        # Match the demo's 4 KiB upper-RAM arena for shell/help and observers.
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes']=4096
        memory_profile=out/'shell-memory.json'
        memory_profile.write_text(json.dumps(profile,indent=2)+'\n')
    p=read_build(out) if reuse else build(t,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            system_mount=None if no_mount else 'D1',dos_mounts=[] if no_mount else getattr(external,'mounts',[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1)]),
            image_data=[],memory_profile=memory_profile)
    media=out/'volume.atr'
    if external:external.prepare(t,out,mode,size)
    else:shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media)
    digest=sha256(media)
    require(sha256(bridge_build/'AltirraBridgeServer')==pin['emulator']['sha256'],'Wrong shell key bridge')
    def at(name):return next(d['address']for d in p['image']['data']if '_SHELLAPP_'+name.upper()+'_' in d['name'])
    schedule=[];observations=[];expected=bytearray();line=bytearray();counts={};state={}
    with emulator(bridge_build,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        for k,v in pin['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        b.config('diskemu','fastest')
        if not no_mount:b.mount(0,str(media))
        if external and hasattr(external,'mount_extra'):external.mount_extra(b,out)
        def far(addr,n):
            result=bytearray()
            for i in range(0,n,2):
                v=b.eval_expr(f'dw(${addr+i:x})');result.extend((v&65535).to_bytes(2,'little'))
            return bytes(result[:n])
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16)in(p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Shell stopped before checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],LIMITS['checkpoint_guest_frames'],LIMITS['checkpoint_host_seconds'],condition)
            finally:b.regs=original
        def frames(n=2):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def key(name,value):
            require(b._cmd_ok(f'KEY {name} {value}')['raw_scan'],'Not physical keys')
            schedule.append(dict(key=name,state=value,frame=b.eval_expr('@frame')))
        def press(c,ctrl=False):
            prev=b.peek16(at('consumed'))
            route=p['build']['memory']['console_storage']['CAPTURE']+28
            old_route=far(route,4) if c=='\x03' else None
            name,shift=KEYS[c] if c not in ('\x03','\x04') else ('BREAK' if c=='\x03' else 'D',False)
            if ctrl:name='D' if c=='\x04' else 'C';key('CTRL','down')
            if shift:key('SHIFT','down')
            key(name,'down')
            if c=='\x03':
                low=int.from_bytes(old_route[:2],'little');high=int.from_bytes(old_route[2:],'little')
                rendezvous(f'(dw(${route:x})!={low})|(dw(${route+2:x})!={high})')
            else:rendezvous(f'dw(${at("consumed"):x})={prev+1}')
            key(name,'up')
            if shift:key('SHIFT','up')
            if ctrl:key('CTRL','up')
            frames()
        def queued(c):
            name,shift=KEYS[c]
            if shift:key('SHIFT','down')
            key(name,'down');frames();key(name,'up')
            if shift:key('SHIFT','up')
            frames()
        def check_screen(stage):
            print('Shell screen',stage,flush=True)
            cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE']
            cells,physical,cursor=terminal(expected)
            rendezvous(f'(db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0)&(dw(${cs["PRESENTATION"]+10:x})={cursor})')
            pointer=int.from_bytes(far(instance,3),'little')
            actual=read_cells(far,instance);screen=b.memdump(state['screen'],960)
            (out/(stage+'.cells.bin')).write_bytes(actual);(out/(stage+'.screen.bin')).write_bytes(screen)
            require(actual==cells,'Retained shell text differs at '+stage)
            require(screen==physical,'Physical shell text differs at '+stage)
            require(int.from_bytes(far(at('captureCount'),4),'little')==len(expected),'Write count differs at '+stage)
            observations.append(dict(stage=stage,frame=b.eval_expr('@frame'),cursor=cursor,length=len(line),output_bytes=len(expected),cells_sha256=sha256(out/(stage+'.cells.bin')),screen_sha256=sha256(out/(stage+'.screen.bin'))))
        def append(text):
            for c in text:
                press(c)
                if c=='\b':
                    if line:
                        old=bytes(line);line.pop();expected.extend(draw(line,old))
                else:line.extend(b' ' if c=='\t' else c.encode());expected.extend(draw(line))
        def submit(output=b'',error=0,exit=False,status=None,diagnostic=None):
            previous=b.peek16(at('commandCount'))
            press('\n');rendezvous(f'dw(${at("commandCount"):x})={previous+1}')
            if not exit:ready()
            name=diagnostic or (re.split(r'[\s|]',bytes(line).decode())[0] if line else 'Shell')
            expected.extend(b'\n'+output);line.clear()
            if error and error!=304:expected.extend(diagnostic_text(error,name))
            elif not error and status not in (None,0,5):expected.extend(f'{name}: Command returned {status}\n'.encode())
            if not exit:expected.extend(draw(line))
            pointer=state['shell'];actual=int.from_bytes(far(pointer+32,4),'little',signed=True);cause=int.from_bytes(far(pointer+36,4),'little',signed=True)
            require((actual,cause)==((status if status is not None else (10 if error else 0)),error),f'Wrong command result {actual}/{cause}; wanted {error}')
        def command(text,output=b'',error=0,exit=False,status=None,diagnostic=None):append(text);submit(output,error,exit,status,diagnostic)
        def ready():
            rendezvous(f'db(${p["build"]["memory"]["console_storage"]["INSTANCE"]+51:x})=2')
        def cancel(ctrl=False):
            press('\x03',ctrl);ready();expected.extend(b'\n');line.clear();expected.extend(draw(line))
        def before(b):
            state.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));state['bytes']=b.memdump(state['screen'],960)
            b._cmd_ok('KEY ALL up');rendezvous(f'db(${at("stage"):x})=1');state['shell']=int.from_bytes(far(at('shell'),3),'little')
            handle=int.from_bytes(far(state['shell'],3),'little');state['cooked']=int.from_bytes(far(handle+16,3),'little')
            expected.extend(diagnostic_text(218,'Shell') if no_mount else b'');expected.extend(draw(line))
            ts=p['build']['task_storage'];created=b.eval_expr(f'dw(${ts["CREATED"]:x})');live=b.eval_expr(f'db(${ts["LIVE"]:x})')
            require((created,live)==((1,2)if no_mount else(3,4)),f'Unexpected shell Task count: {created}/{live}')
            observations.append(dict(stage='startup',created=created,live=live,shell_pointer=state['shell']))
            check_screen('initial');b.poke(at('gate'),1)
            command('echo "hello world"',b'hello world\n');check_screen('quoted-echo')
            if history_unavailable:
                command('echo editX\bed',b'edited\n');check_screen('history-unavailable')
                attempts=next(d['address'] for d in p['image']['data'] if '_COOKEDLINE_ENABLEATTEMPTS_' in d['name'])
                require(b.peek16(attempts)==1,'Shell retried unavailable history')
                require(int.from_bytes(far(state['cooked']+407,3),'little')==0,
                        'History allocated after injected failure')
                counts['history_enable_attempts']=1
            if external:
                from types import SimpleNamespace
                external.exercise(SimpleNamespace(command=command,check_screen=check_screen,append=append,press=press,
                    rendezvous=rendezvous,ready=ready,far=far,at=at,p=p,state=state,expected=expected,line=line,b=b))
            elif not smoke:
                command('help',b'HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT DEVICES PATH ALIAS UNALIAS RUN JOBS BREAK EXIT\nEdit: Ctrl-A/E home/end, B/F left/right\nCtrl-U clear, K cut end, W cut word\nCtrl-L clear screen\nHistory: Ctrl-P/N or Atari up/down\nAtari left/right move the cursor\n')
                command('cd',b'' if no_mount else b'D1:\n',211 if no_mount else 0)
                if not no_mount:
                    for cmd in ('cd tools/sub','cd /','cd :','cd d1:tools','cd missing'):
                        command(cmd,error=205 if cmd.endswith('missing') else 0)
                    command('cd',b'D1:TOOLS\n')
                else:command('cd D1:',error=218)
                command('echo "a**b*"c"',b'a*b"c\n')
                for text,error in [('unknown',211 if no_mount else 205),('echo "bad',115),('echo "bad*x"',115),('echo a|b',115),('echo a;b',115),('echo>NIL:',115),('echo >',115),('help extra',115),('echo '+' '.join(['x']*16),115)]:
                    command(text,error=error,diagnostic='Shell' if error==115 else None)
                append('a');check_screen('one');cancel(ctrl=True)
                append('a'*36);check_screen('thirty-six');append('b');check_screen('thirty-seven');append('\b');check_screen('back-to-thirty-six');cancel()
                append('echo '+'a'*250);check_screen('max-line');submit(b'a'*250+b'\n');check_screen('max-command')
                append('echo '+'a'*250);press('b');expected.extend(draw(b'',bytes(line)));check_screen('overflow')
                press('\n');ready();expected.extend(b'\n'+diagnostic_text(120,'Shell'));line.clear();expected.extend(draw(line))
                append('echo\ttab');submit(b'tab\n');check_screen('tab')
                # Pause only in the fixture, after an actual translated key.
                # The console worker continues to accept real typeahead.
                b.poke(at('suspend'),1);append('e')
                require(b.peek(at('stage'))==bytes([4]),'No typeahead rendezvous')
                consumed=b.peek16(at('consumed'))
                for c in 'cho queued\n':queued(c)
                b.poke(at('gate'),1)
                rendezvous(f'dw(${at("consumed"):x})={consumed+11}');ready()
                for c in 'cho queued':line.extend(c.encode());expected.extend(draw(line))
                expected.extend(b'\nqueued\n');line.clear();expected.extend(draw(line))
                check_screen('typeahead')
                append('echo DO');b.poke(at('suspend'),1);append('N')
                for i in range(129):queued('a')
                instance=p['build']['memory']['console_storage']['INSTANCE']
                require(b.eval_expr(f'db(${instance+32:x})')==1,'FIFO did not overflow')
                b.poke(at('gate'),1)
                rendezvous(f'db(${state["cooked"]+12:x})=1');ready()
                expected.extend(draw(b'',bytes(line)));line.clear()
                # Neither the surviving suffix nor Ctrl-C may end loss resync.
                for c in 'exit':press(c)
                press('\x03',ctrl=True)
                require(b.eval_expr(f'db(${state["cooked"]+12:x})')==1,'Ctrl-C ended input-loss resync')
                expected.extend(draw(b''))
                press('\n');ready();expected.extend(b'\nInput lost; line discarded\n');expected.extend(draw(line))
                command('echo recovered',b'recovered\n');check_screen('input-loss-resync')
            if eof:
                if eof=='partial':append('echo final')
                press('\x04',True);rendezvous(f'db(${at("stage"):x})=2')
                expected.extend(b'\n'+(b'final\n' if eof=='partial' else b''));line.clear()
            else:command('exit',exit=True)
            check_screen('exit')
            require(b.peek(at('stage'))==bytes([2]),'Missing exit rendezvous')
            counts['consumed']=b.peek16(at('consumed'));counts['output_bytes']=len(expected)
            b.poke(at('gate'),1);b.bp_clear_all()
            collect_capture(b,p,out)
        try:rt,_=execute(b,p,before_run=before,timeout=LIMITS['completion_host_seconds'],frame_limit=LIMITS['completion_guest_frames'])
        except Exception:
            print('Shell failure checks/stage',data(b,p['image'],'checks',True),data(b,p['image'],'stage'),flush=True)
            if state.get('shell'):print('Shell state',far(state['shell'],128).hex(),flush=True)
            raise
        require(data(b,p['image'],'stage')==[3],'Incomplete shell exit')
        actual=(out/'writes.bin').read_bytes()
        require(actual==expected,'Exact shell Write payload differs')
        require(b.memdump(state['screen'],960)==state['bytes'] and b.peek(752)==state['cursor'] and b.peek(16)==state['mask'],'Shell did not restore OS console')
        ownership(b,p,out);require(sha256(media)==digest,'Shell modified media')
        if external and hasattr(external,'persisted'):external.persisted(b,p,out)
    return dict(status='pass',mode=mode,kernel_bank=bank,sector_bytes=size,no_mount=no_mount,smoke=smoke,eof=eof,history_unavailable=history_unavailable,build=p['build'],runtime=rt,machine=machine,pin=pin,limits=LIMITS,observations=observations,schedule=schedule,counts=counts,media_sha256=digest,writes_sha256=sha256(out/'writes.bin'),source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell.act','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','tests/programs/shell_core.act','tools/test_shell_core.py')},hook_sha256=sha256(out/'shell-observed.inc'))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--bank',type=int,default=1);a.add_argument('--sector-size',type=int,default=128);a.add_argument('--no-mount',action='store_true');a.add_argument('--smoke',action='store_true');a.add_argument('--history-unavailable',action='store_true');a.add_argument('--paced',action='store_true');a.add_argument('--eof',choices=('empty','partial'));a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if args.paced else None
    bridge=ROOT/'build/shell-paced-bridge' if args.paced else None
    try:r=run(compiler(args.compiler_dir),out,args.case,args.bank,args.sector_size,args.no_mount,args.smoke,args.eof,history_unavailable=args.history_unavailable,pin=pin,bridge_build=bridge)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Shell core passed',args.case,flush=True)
