#!/usr/bin/env python3
"""Real resident shell with private allocation/selector/close failure controls."""
from library_paths import library_file, read_source
import argparse,json,shutil
from pathlib import Path
import generate_tasks
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read as far_read
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
LIMITS=dict(host_seconds=240,guest_frames=12000)

def run(t,out,mode,bank=2,scenario=0):
    out.mkdir(parents=True,exist_ok=True)
    session=(ROOT/'examples/shell/shell-session.inc').read_text().replace('DOS.CurrentDir(', 'TestDirectory(').replace('DOS.SelectOutput(', 'TestOutput(').replace('DOS.BeginForeground(', 'TestForeground(')
    dispatch='          ShellDispatch()'
    require(session.count(dispatch)==1,'Missing shell dispatch hook')
    session=session.replace(dispatch,'          TestDispatch(0)')
    session=session.replace('"shell-commands.inc"','"'+str(ROOT/'examples/shell/shell-commands.inc')+'"')
    redirection=(ROOT/'examples/shell/shell-redirection.inc').read_text().replace('DOS.SelectOutput(', 'TestOutput(').replace('DOS.Close(', 'TestClose(')
    session=session.replace('"shell-execute.inc"','"'+str(ROOT/'examples/shell/shell-execute.inc')+'"')
    session=session.replace('INCLUDE "shell-jobs.inc"','INCLUDE "'+str(ROOT/'examples/shell/shell-jobs.inc')+'"')
    (out/'shell-redirection.inc').write_text(redirection);(out/'shell-lifetime.inc').write_text(session)
    source=out/'shell_lifetime.act';source.write_bytes((ROOT/'tests/programs/shell_lifetime.act').read_bytes())
    shutil.copyfile(ROOT/'tests/programs/shellfaultcontrol.act',out/'shellfaultcontrol.act')
    original=generate_tasks.policy_modules
    def instrument(output,*args,**kwargs):
        directory=Path(original(output,*args,**kwargs))
        changes={
            'dosclient': [('  client=ClientContext POINTER(EXEC.AllocMem', '  SHELLFAULTCONTROL.contextAttempts==+1\n  client=ClientContext POINTER(EXEC.AllocMem'),('  client.port=EXEC.CreateMsgPort()', '  SHELLFAULTCONTROL.portAttempts==+1\n  client.port=EXEC.CreateMsgPort()')],
            'fslocks': [('  LET item=FSTYPES.LockObject POINTER(EXEC.AllocMem', '  IF SHELLFAULTCONTROL.failLock<>0 THEN SHELLFAULTCONTROL.failLock=0 RETURN(NULL) FI\n  LET item=FSTYPES.LockObject POINTER(EXEC.AllocMem')]}
        for name,edits in changes.items():
            path=directory/(name+'.act');s=read_source(library_file(name+'.act'))
            s=s.replace('USE EXEC','USE EXEC\nUSE SHELLFAULTCONTROL',1)
            for a,b in edits:require(s.count(a)==1,'Stale private hook '+a);s=s.replace(a,b)
            path.write_text(s)
        shutil.copyfile(ROOT/'tests/programs/shellfaultcontrol.act',directory/'shellfaultcontrol.act')
        return directory
    generate_tasks.policy_modules=instrument
    try:p=build(t,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,
                system_mount='D1',dos_mounts=[dict(alias=f'D{i+1}',unit=49+i,sectors=720,sector_bytes=128,profile=1)for i in range(2)],image_data=[(0xe1000,bytes(2048))])
    finally:generate_tasks.policy_modules=original
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);digest=sha256(media)
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned shell emulator')
    def at(name):return next(d['address']for d in p['image']['data']if '_SHELLAPP_'+name.upper()+'_'in d['name'])
    saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media));b.mount(1,str(media))
        def before(b):
            saved.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['bytes']=b.memdump(saved['screen'],960);b.poke(at('scenario'),scenario)
        try:rt,_=execute(b,p,before_run=before,expected_status=4 if scenario==3 else 0,timeout=LIMITS['host_seconds'],frame_limit=LIMITS['guest_frames'])
        except Exception:
            ptr=int.from_bytes(bytes(data(b,p['image'],'shell')),'little')
            print('Shell lifetime checks',data(b,p['image'],'checks',True),'commands',data(b,p['image'],'commands',True),'events',data(b,p['image'],'events',True),'allocations',data(b,p['image'],'contextAttempts',True),data(b,p['image'],'portAttempts',True),'shell',ptr,'state',[b.eval_expr(f'dw(${ptr+i:x})')for i in (24,28,54)]if ptr else [],flush=True);raise
        counts={k:int.from_bytes(bytes(data(b,p['image'],k)),'little')for k in ('checks','commands','events')}
        raw=far_read(b,0xe1000,counts['events']*32,out);events=[]
        for offset in range(0,len(raw),32):
            a=raw[offset:offset+32];events.append(dict(tag=a[0],status=int.from_bytes(a[1:5],'little',signed=True),error=int.from_bytes(a[5:9],'little',signed=True),done=a[9],redirect_active=a[10],restore_failure=a[11],temporary_input=a[12],temporary_output=a[13],input_console=a[14],output_console=a[15],objects=a[16],busy=a[17],directory=a[18],endpoint_references=a[19],endpoint_active=a[20]))
        if scenario==3:
            pointer=int.from_bytes(bytes(data(b,p['image'],'shell')),'little');require(pointer and events[-1]['objects']==2 and events[-1]['directory']==1,'Guard did not retain shell ownership')
        else:
            require(data(b,p['image'],'finished')==[1],'Incomplete shell lifetime');ownership(b,p,out)
            require(b.memdump(saved['screen'],960)==saved['bytes']and b.peek(752)==saved['cursor']and b.peek(16)==saved['mask'],'OS console not restored')
        require(sha256(media)==digest,'Read-only media changed')
    return dict(status='pass',mode=mode,bank=bank,scenario=scenario,build=p['build'],runtime=rt,pin=PIN,machine=machine,counts=counts,events=events,limits=LIMITS,media_sha256=digest,
        hooks={str(f.relative_to(out)):sha256(f)for f in (out/'shell-lifetime.inc',out/'shell-redirection.inc',out/'task-kernel/dosclient.act',out/'task-kernel/fslocks.act')},
        source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell.act','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tests/programs/shell_lifetime.act','tests/programs/shellfaultcontrol.act','tools/test_shell_lifetime.py')})
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--scenario',type=int,default=0);a.add_argument('--bank',type=int,default=2);a.add_argument('--output',type=Path,required=True);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');o=a.parse_args();r=run(compiler(o.compiler_dir),o.output.resolve(),o.case,o.bank,o.scenario);(o.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell lifetime passed',o.case,o.bank,o.scenario,flush=True)
