#!/usr/bin/env python3
"""Build and execute the shipped resident entry without test hooks."""
from shell_inspect import address as shell_address
import adapter_state as adapter
import argparse,json,re,time
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_shell_core import PIN,KEYS,draw,diagnostic_text
from test_console_display import terminal
from make_shell_disk import make as make_disk, SOURCE as DISK_SOURCE

from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def run(t,out,mode,no_mount=False,paced=False,invalid_disk=False,stack_checks=None,redirection=False,reuse=False):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())if paced else PIN
    bridge=ROOT/('build/shell-paced-bridge'if paced else 'build/shell-console-bridge')
    out.mkdir(parents=True,exist_ok=True)
    mounts=[]if no_mount else json.loads((ROOT/'config/shell-mydos.json').read_text())['mounts']
    diskemu={1:'fastest',4:'generic56k'}[mounts[0]['profile']]if mounts else 'generic56k'
    # Controller registry plus the shared shell/runtime use an 8 KiB test arena.
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory_profile=out/'shell-memory.json'
    memory_profile.write_text(json.dumps(profile,indent=2)+'\n')
    p=read_build(out) if reuse else build(t,ROOT/'examples/shell/shell.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,
            dos_mounts=mounts,system_mount=None if no_mount else 'D1',stack_checks=stack_checks,memory_profile=memory_profile)
    session=(ROOT/'examples/shell/shell-session.inc').read_text()
    transfer_offset=sum(int(re.search(r'^CONST '+name+r'=(\d+)$',session,re.M).group(1))
                        for name in ('HEADER_SIZE','LINE_CAPACITY','DRAW_CAPACITY','SCRATCH_CAPACITY'))
    media=out/'volume.atr';files=make_disk(media)
    if invalid_disk:
        raw=bytearray(media.read_bytes());raw[16+359*128]=0;media.write_bytes(raw)
    def at(name):return shell_address(p['image'],name,"SHELLAPP")
    state={};schedule=[];payload=bytearray()
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin)as b:
        require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned shell bridge')
        for k,v in pin['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin);b.config('diskemu',diskemu)
        if not no_mount:b.mount(0,str(media))
        cs=p['build']['memory']['console_storage'];ready=cs['INSTANCE']+51
        def wait(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            run_to(b,p['labels']['native_nmi'],12000,240,condition)
        def key(name,value):
            require(b._cmd_ok(f'KEY {name} {value}')['raw_scan'],'Nonphysical entry input');schedule.append(dict(key=name,state=value,frame=b.eval_expr('@frame')))
        def before(b):
            state.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));state['bytes']=b.memdump(state['screen'],960)
            # The console adopts the loader's retained text and cursor.
            position=b.peek16(94)-state['screen']
            native=bytearray(state['bytes']);native[position]=b.peek(93)[0]
            initial=(bytes(v+32 if v<64 else v if 97<=v<=122 or v==124 else 63
                           for v in (n&127 for n in native)),position)
            b._cmd_ok('KEY ALL up');wait(f'db(${ready:x})=2')
            pointer=b.eval_expr(f'dw(${at("shell"):x})')|(b.eval_expr(f'db(${at("shell")+2:x})')<<16)
            handle=b.eval_expr(f'dw(${pointer:x})')|(b.eval_expr(f'db(${pointer+2:x})')<<16)
            cooked=b.eval_expr(f'dw(${handle+16:x})')|(b.eval_expr(f'db(${handle+18:x})')<<16)
            error=218 if no_mount else 225 if invalid_disk else 0
            identity=p['build']['exec_build']
            strings=identity['strings']
            banner='\n'+strings['banner']+strings['slots']+strings['stackChecks']+'console.device: ready\n'+strings['mountStart']
            banner+='\n'+strings['mountFailure']+'\n\n'+diagnostic_text(error,'Shell').decode()if error else 'SYS: -> D1: ready, read-only'+strings['otherMountsReady']+'\n\n'
            payload.extend(banner.encode());payload.extend(draw(b''))
            require(b.eval_expr(f'dw(${pointer+36:x})')==error,'Startup result differs')
            def screen(stage):
                cells,physical,cursor=terminal(payload,initial);instance=cs['INSTANCE']
                wait(f'(db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0)&(dw(${cs["PRESENTATION"]+10:x})=dw(${instance+54:x})+dw(${instance+10:x}))')
                actual=b.memdump(state['screen'],960)
                if actual!=physical:
                    (out/'screen-actual.bin').write_bytes(actual)
                    (out/'screen-expected.bin').write_bytes(physical)
                require(actual==physical,stage+' screen differs')
                return physical,cursor
            boot_screen,_=screen('Startup');(out/'boot.screen.bin').write_bytes(boot_screen)
            wait(f'@frame>={b.eval_expr("@frame")+2}');(out/'boot.png').write_bytes(b.screenshot())
            state['banner']=banner;state['command_times']=[]
            line=bytearray()
            version=strings['version'].encode()
            mounts_output=b'MOUNT FILESYSTEM ACCESS    STATE DEVICE/UNIT\n'+(b'No mounted filesystems\n'if error else b'D1:   MyDOS      read-only mounted sio.device/D1\nRAM:  RAM        writable  mounted\n')
            devices_output=b'DEVICE          STATE\nconsole.device  ready\nsio.device      '+(b'inactive'if no_mount else b'ready')+b'\ntimer.device    ready\nideplus.device  inactive\n'
            state.update(mounts_output=mounts_output.decode(),devices_output=devices_output.decode())
            commands=[('help',b'HELP ECHO CLS CD DIR TYPE MEM TASKS VER MOUNT UNMOUNT DEVICES PATH ALIAS UNALIAS RUN JOBS BREAK EXECUTE NEWSHELL SESSIONS SESSION EXIT\nEdit: Ctrl-A/E home/end, B/F left/right\nCtrl-U clear, K cut end, W cut word\nCtrl-L clear screen\nHistory: Ctrl-P/N or Atari up/down\nAtari left/right move the cursor\nTAB completes commands and files\n',0),
                ('ver',version,0),('ver >nil:',b'',0),('ver extra',diagnostic_text(115,'Shell'),115),
                ('tasks',None,0),('tasks >nil:',b'',0),('tasks extra',diagnostic_text(115,'Shell'),115),
                ('mount',mounts_output,0),('mount >nil:',b'',0),('mount D2: invalid',diagnostic_text(311,'mount'),311),
                ('devices',devices_output,0),('devices >nil:',b'',0),('devices extra',diagnostic_text(115,'Shell'),115),
                ('echo ok',b'ok\n',0),('cd SYS:',diagnostic_text(error,'cd')if error else b'',error)]
            if not error:
                # MyDOS directory rows expose a sector-rounded size bound.
                payload_bytes=mounts[0]['sector_bytes']-3
                def size_bound(name):
                    return ((len(files[name])+payload_bytes-1)//payload_bytes)*payload_bytes
                listing=f"C/\nDOCS/\nHELLO.TXT <={size_bound('HELLO.TXT')}\nREADME.TXT <={size_bound('README.TXT')}\nS/\nTOOLS/\n".encode()
                commands.extend([('dir',listing,0),('type hello.txt',files['HELLO.TXT'],0),
                    ('type readme.txt',files['README.TXT'],0),('cd docs',b'',0),
                    ('type commands.txt',files['DOCS/COMMANDS.TXT'],0),('cd :',b'',0),
                    ('dir tools',b'SUB/\n',0),('cd tools/sub',b'',0),
                    ('type note.txt',files['TOOLS/SUB/NOTE.TXT'],0),('cd :',b'',0)])
            if invalid_disk and not redirection:
                commands.extend([('cd sys:',b'',0),('type SYS:HELLO.TXT',files['HELLO.TXT'],0)])
            commands.append(('exit',b'',0))
            if redirection:
                commands=[('type <D1:HELLO.TXT >NIL:',diagnostic_text(error,'Shell') if error else b'',error),
                    ('cd TOOLS >NIL:',diagnostic_text(error,'cd') if error else b'',error),
                    ('echo "<ok>"',b'<ok>\n',0),('echo cooked >CON:',b'cooked\n',0),
                    ('type <NIL: >NIL:',b'',0),('exit >NIL:',b'',0)]
            state['commands']=[c[0]for c in commands]
            for command,output,error in commands:
                if invalid_disk and command=='cd sys:':
                    replacement=out/'replacement.atr'
                    make_disk(replacement)
                    b.mount(0,str(replacement))
                for c in command:
                    name,shift=KEYS[c]
                    if shift:key('SHIFT','down')
                    key(name,'down');line.extend(c.encode())
                    wait(f'(dw(${cooked+2:x})={len(line)})&(db(${ready:x})=2)');payload.extend(draw(line))
                    key(name,'up')
                    if shift:key('SHIFT','up')
                    wait(f'@frame>={b.eval_expr("@frame")+2}')
                if command.startswith('exit'):break
                started=time.monotonic();frame=b.eval_expr('@frame')
                key('RETURN','down');wait(f'@frame>={frame+2}');key('RETURN','up')
                wait(f'(dw(${pointer+40:x})=0)&(dw(${cooked+2:x})=0)&(db(${ready:x})=2)')
                state['command_times'].append(dict(command=command,host_seconds=time.monotonic()-started,guest_frames=b.eval_expr('@frame')-frame))
                if command=='tasks':
                    names=['shell controller','console.device']+([]if no_mount else ['sio.device'])+([]if no_mount or invalid_disk else ['dos.filesystem'])+['shell']
                    states={1:'READY',3:'RUNNING',4:'SLEEPING',5:'WAITING'}
                    rows=[]
                    seen=set();previous_slot=-1
                    # Lazy driver startup can change which worker gets a slot.
                    # TASKS reports the snapshot's actual ascending slot order.
                    for index in range(len(names)):
                        raw=bytes(b.eval_expr(f'db(${pointer+transfer_offset+index*26+i:x})')for i in range(26))
                        slot=raw[0]
                        actual_name=raw[2:].split(b'\0',1)[0].decode('ascii')
                        require(previous_slot<slot<8 and actual_name in names and actual_name not in seen,
                                f'Task snapshot identity differs: ({slot}, {actual_name})')
                        require((slot==0)==(actual_name=='shell controller'),'Task snapshot root differs')
                        require(raw[1]==3 if actual_name=='shell' else raw[1]in (1,5),'Task snapshot state differs')
                        seen.add(actual_name);previous_slot=slot
                        rows.append(f'{slot:<4} {states[raw[1]]:<8} {actual_name}\n')
                    output=('SLOT STATE    NAME\n'+''.join(rows)).encode()
                    state['tasks_output']=output.decode()
                line.clear();payload.extend(b'\n'+output);payload.extend(draw(line))
                require(b.eval_expr(f'dw(${pointer+32:x})')==(10 if error else 0) and b.eval_expr(f'dw(${pointer+36:x})')==error,'Entry command result differs: '+command)
                screen(command)
            _,cursor=screen('Shipped shell')
            state['before_exit_cursor']=cursor
            key('RETURN','down');b.bp_clear_all()
        rt,_=execute(b,p,before_run=before,timeout=300,frame_limit=15000)
        key('RETURN','up')
        require(data(b,p['image'],'exitStatus')==[0,0,0,0],'Shipped shell exit failed')
        require(b.memdump(state['screen'],960)==state['bytes'] and b.peek(752)==state['cursor'] and b.peek(16)==state['mask'],'Entry did not restore OS')
        ownership(b,p,out)
    return dict(status='pass',mode=mode,no_mount=no_mount,redirection=redirection,invalid_disk=invalid_disk,build=p['build'],runtime=rt,machine=machine,pin=pin,schedule=schedule,
                banner=state['banner'],tasks_output=state.get('tasks_output'),mounts_output=state['mounts_output'],devices_output=state['devices_output'],command_times=state['command_times'],commands=state['commands'],diskemu=diskemu,before_exit_cursor=state['before_exit_cursor'],media_sha256=sha256(media),source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell.act','examples/shell/shell-boot.inc','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','lib/fs/fsinspect.act','lib/io/deviceinspect.act','tools/test_shell_entry.py','tools/make_shell_disk.py','config/shell-mydos.json')},disk_inputs={str(s.relative_to(ROOT)):sha256(s)for s in DISK_SOURCE.rglob('*')if s.is_file()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--no-mount',action='store_true');p.add_argument('--invalid-disk',action='store_true');p.add_argument('--paced',action='store_true');p.add_argument('--stack-checks',action=argparse.BooleanOptionalAction,default=None);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.no_mount,a.paced,a.invalid_disk,a.stack_checks,reuse=a.reuse);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell entry passed',a.case,flush=True)
