#!/usr/bin/env python3
"""Build and execute the shipped resident entry without test hooks."""
import argparse,json,time
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_shell_core import PIN,KEYS,draw
from test_console_display import terminal
from make_shell_disk import make as make_disk, SOURCE as DISK_SOURCE

def run(t,out,mode,no_mount=False,paced=False,invalid_disk=False,stack_checks=None,redirection=False):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())if paced else PIN
    bridge=ROOT/('build/shell-paced-bridge'if paced else 'build/shell-console-bridge')
    out.mkdir(parents=True,exist_ok=True)
    mounts=[]if no_mount else json.loads((ROOT/'config/shell-mydos.json').read_text())['mounts']
    diskemu={1:'fastest',4:'generic56k'}[mounts[0]['profile']]if mounts else 'generic56k'
    p=build(t,ROOT/'examples/shell/shell.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,
            dos_mounts=mounts,system_mount=None if no_mount else 'D1',stack_checks=stack_checks)
    media=out/'volume.atr';files=make_disk(media)
    if invalid_disk:
        raw=bytearray(media.read_bytes());raw[16+359*128]=0;media.write_bytes(raw)
    def at(name):return next(d['address']for d in p['image']['data']if '_SHELLAPP_'+name.upper()+'_'in d['name'])
    state={};schedule=[];payload=bytearray()
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin)as b:
        require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned shell bridge')
        for k,v in pin['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin);b.config('diskemu',diskemu)
        if not no_mount:b.mount(0,str(media))
        cs=p['build']['memory']['console_storage'];ready=cs['INSTANCE']+51
        def wait(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition='dw($2000)!=$ffff')
            run_to(b,p['labels']['native_nmi'],12000,240,condition)
        def key(name,value):
            require(b._cmd_ok(f'KEY {name} {value}')['raw_scan'],'Nonphysical entry input');schedule.append(dict(key=name,state=value,frame=b.eval_expr('@frame')))
        def before(b):
            state.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));state['bytes']=b.memdump(state['screen'],960)
            b._cmd_ok('KEY ALL up');wait(f'db(${ready:x})=2')
            pointer=b.eval_expr(f'dw(${at("shell"):x})')|(b.eval_expr(f'db(${at("shell")+2:x})')<<16)
            handle=b.eval_expr(f'dw(${pointer:x})')|(b.eval_expr(f'db(${pointer+2:x})')<<16)
            cooked=b.eval_expr(f'dw(${handle+16:x})')|(b.eval_expr(f'db(${handle+18:x})')<<16)
            error=218 if no_mount else 225 if invalid_disk else 0
            identity=p['build']['exec_build']
            banner=f"Exec816 ({identity['display']})\n\nexec: 8 task slots\nconsole.device: ready\n"
            banner=banner.replace('console.device: ready',f'exec: stack checks {"enabled" if p["build"]["stack_checks"] else "disabled"}\nconsole.device: ready')
            if no_mount:banner+='SYS: no system volume configured\n'
            else:banner+='sio.device: D1 ready, 57.6k profile\nSYS: mounting...\n'
            banner+='SYS: mount failed; use CD SYS: to retry\n\nError '+str(error)+'\n'if error else 'SYS: -> D1: ready, read-only\n\n'
            payload.extend(banner.encode());payload.extend(draw(b''))
            require(b.eval_expr(f'dw(${pointer+36:x})')==error,'Startup result differs')
            def screen(stage):
                cells,physical,cursor=terminal(payload);instance=cs['INSTANCE']
                wait(f'(dw(${instance+14:x})>=dw(${instance+16:x}))&(dw(${cs["PRESENTATION"]+10:x})={cursor})')
                require(b.memdump(state['screen'],960)==physical,stage+' screen differs')
                return physical,cursor
            initial,_=screen('Startup');(out/'boot.screen.bin').write_bytes(initial)
            wait(f'@frame>={b.eval_expr("@frame")+2}');(out/'boot.png').write_bytes(b.screenshot())
            state['banner']=banner;state['command_times']=[]
            line=bytearray()
            pin_revision=json.loads((ROOT/'toolchain/actionc.json').read_text())['revision']
            version=f"Exec816 ({identity['display']})\nactionc pin: {pin_revision[:7]}\n".encode()
            mounts_output=b'MOUNT FILESYSTEM ACCESS    STATE\n'+(b'No mounted filesystems\n'if error else b'D1:   MyDOS      read-only mounted\n')
            devices_output=b'DEVICE          STATE\nconsole.device  ready\nsio.device      '+(b'inactive'if no_mount else b'ready')+b'\n'
            state.update(mounts_output=mounts_output.decode(),devices_output=devices_output.decode())
            commands=[('help',b'HELP ECHO CD DIR TYPE MEM TASKS VER MOUNT DEVICES EXIT\n',0),
                ('ver',version,0),('ver >nil:',b'',0),('ver extra',b'Error 115\n',115),
                ('tasks',None,0),('tasks >nil:',b'',0),('tasks extra',b'Error 115\n',115),
                ('mount',mounts_output,0),('mount >nil:',b'',0),('mount D2:',b'Error 115\n',115),
                ('devices',devices_output,0),('devices >nil:',b'',0),('devices extra',b'Error 115\n',115),
                ('echo ok',b'ok\n',0),('cd SYS:',f'Error {error}\n'.encode()if error else b'',error)]
            if not error:
                listing=f"DOCS/\nHELLO.TXT {len(files['HELLO.TXT'])}\nREADME.TXT {len(files['README.TXT'])}\nTOOLS/\n".encode()
                commands.extend([('dir',listing,0),('type hello.txt',files['HELLO.TXT'],0),
                    ('type readme.txt',files['README.TXT'],0),('cd docs',b'',0),
                    ('type commands.txt',files['DOCS/COMMANDS.TXT'],0),('cd :',b'',0),
                    ('dir tools',b'SUB/\n',0),('cd tools/sub',b'',0),
                    ('type note.txt',files['TOOLS/SUB/NOTE.TXT'],0),('cd :',b'',0)])
            if invalid_disk and not redirection:
                commands.extend([('cd sys:',b'',0),('type SYS:HELLO.TXT',files['HELLO.TXT'],0)])
            commands.append(('exit',b'',0))
            if redirection:
                commands=[('type <D1:HELLO.TXT >NIL:',f'Error {error}\n'.encode() if error else b'',error),
                    ('cd TOOLS >NIL:',f'Error {error}\n'.encode() if error else b'',error),
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
                    names=['shell','console.device']+([]if no_mount else ['sio.device'])+([]if no_mount or invalid_disk else ['dos.filesystem'])
                    states={1:'READY',3:'RUNNING',4:'SLEEPING',5:'WAITING'}
                    rows=[]
                    for slot,name in enumerate(names):
                        raw=bytes(b.eval_expr(f'db(${pointer+776+slot*26+i:x})')for i in range(26))
                        actual_name=raw[2:].split(b'\0',1)[0].decode('ascii')
                        require(raw[0]==slot and actual_name==name,'Task snapshot identity differs')
                        require(raw[1]==3 if slot==0 else raw[1]in (1,5),'Task snapshot state differs')
                        rows.append(f'{slot:<4} {states[raw[1]]:<8} {name}\n')
                    output=('SLOT STATE    NAME\n'+''.join(rows)).encode()
                    state['tasks_output']=output.decode()
                line.clear();payload.extend(b'\n'+output);payload.extend(draw(line))
                require(b.eval_expr(f'dw(${pointer+32:x})')==(10 if error else 0) and b.eval_expr(f'dw(${pointer+36:x})')==error,'Entry command result differs')
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
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--no-mount',action='store_true');p.add_argument('--invalid-disk',action='store_true');p.add_argument('--paced',action='store_true');p.add_argument('--stack-checks',action=argparse.BooleanOptionalAction,default=None);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.no_mount,a.paced,a.invalid_disk,a.stack_checks);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell entry passed',a.case,flush=True)
