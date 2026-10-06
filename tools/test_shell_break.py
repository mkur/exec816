#!/usr/bin/env python3
"""Physical shell break, prompt recovery and unchanged SIO gates with eight Tasks."""
import adapter_state as adapter
from library_paths import read_source
import argparse,json,os,shutil,time
from pathlib import Path
from console_model import read_cells
from native_program import ROOT,build,compiler,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from banked_test_memory import read as far_read
from dos_concurrent_trace import call_marker,sector_end_marker
from generate_console import glyphs
from sio_transaction_trace import read_events,BASE_HZ
from console_concurrent_trace import analyze as serial_timing
from shell_break_timing import validate as validate_timing
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES={'compute':(1,'HELP'),'ctrl-c':(1,'HELP'),'typeahead':(1,'HELP'),'queued-type':(2,'TYPE TOOLS/SUB/DATA.BIN >NIL:'),'active-type':(3,'TYPE TOOLS/SUB/DATA.BIN >NIL:'),'directory':(4,'DIR >NIL:'),'cd':(5,'CD TOOLS/SUB'),'redirected-type':(6,'TYPE <TOOLS/SUB/DATA.BIN >NIL:'),'console-write':(7,'TYPE TOOLS/SUB/DATA.BIN')}

def instrument(out,size):
    source=(ROOT/'tests/programs/shell_concurrent.act').read_text()
    source=source[source.index('USE EXEC\n'):source.index('PROC CommandBegin(')]
    source=source.replace('IF good=0 THEN\n    HEAPCORE.Abort($ed00+commands)\n  FI','IF good=0 THEN HEAPCORE.Abort($ed00+(checks & 255)) FI\n  checks==+1')
    source=source.replace('    Check(DOS.Write(DOS.Output(),completion,11)=11)','    ; No background console output while observing the prompt.')
    source=source.replace('    IF mix.floods<30 THEN\n      Flood(0)\n      ticks=EXECTASKS.Sleep(5)\n    ELSE\n      ticks=EXECTASKS.Sleep(1)\n    FI','    ticks=EXECTASKS.Sleep(1)')
    source=source.replace(' AND mix.floods=30','')
    source=source.replace('EXEC.AllocMem(70003,', 'EXEC.AllocMem(probe.expected,').replace('readBuffer,70003)', 'readBuffer,LONGINT(probe.expected))')
    if size==256:
        source=source.replace('BYTE ARRAY readPath=[68 65 84 65 46 66 73 78 0]','BYTE ARRAY readPath=[76 65 82 71 69 46 66 73 78 0]').replace('BYTE ARRAY readBase=[68 49 58 84 79 79 76 83 47 83 85 66 0]','BYTE ARRAY readBase=[68 49 58 0]')
    (out/'shell-break-common.inc').write_text(source)
    for name in ('shell_break.act','breakprobe.act'):(out/name).write_bytes((ROOT/'tests/programs'/name).read_bytes())
    core=(ROOT/'examples/shell/shell-session.inc').read_text()
    for name in ('shell-jobs.inc','shell-commands.inc','shell-redirection.inc'):core=core.replace('"'+name+'"','"'+str(ROOT/'examples/shell'/name)+'"')
    core=core.replace('PROC ShellDispatch()\n  CARD index','PROC ShellDispatch()\n  CARD index\n  IF scenario=1 AND shell.command=1 THEN Compute(0) RETURN FI')
    core=core.replace('  ShellWrite(shell.console,prompt,2)','  BREAKPROBE.Prompt(prompt)\n  ShellWrite(shell.console,prompt,2)\n  BREAKPROBE.Retained(0)')
    (out/'shell-observed.inc').write_text(core)
    requests=read_source(ROOT/'lib/console/console-requests.inc')
    needle='  instance.write=NULL\n'
    require(requests.count(needle)==1,'Missing write completion boundary')
    requests=requests.replace(needle,'  BREAKPROBE.Written(instance,request)\n'+needle)
    (out/'console-requests-probe.inc').write_text(requests)
    driver=read_source(ROOT/'lib/console/consoledriver.act').replace('USE EXEC\n','USE EXEC\nUSE BREAKPROBE\n',1)
    driver=driver.replace(str(ROOT/'lib/console/console-requests.inc'),str(out/'console-requests-probe.inc'))
    driver=driver.replace('"console-storage-action.inc"','"'+str(out/'console-storage-action.inc')+'"')
    needle='        CONSOLEDISPLAY.Present(view,instance)'
    require(driver.count(needle)==1,'Missing display completion boundary')
    driver=driver.replace(needle,needle+'\n        BREAKPROBE.Display(instance)')
    (out/'consoledriver.act').write_text(driver)
    cooked=read_source(ROOT/'lib/dos/doscooked.act').replace('USE EXEC\n','USE EXEC\nUSE BREAKPROBE\n',1)
    cooked=cooked.replace('        state.drawn=0\n      FI','        state.drawn=0\n      FI\n      BREAKPROBE.Key(0)')
    (out/'doscooked.act').write_text(cooked)
    return {name:sha256(out/name) for name in ('shell-break-common.inc','shell-observed.inc','breakprobe.act','consoledriver.act','console-requests-probe.inc','doscooked.act')}

def markers(p):
    names=('native_nmi','native_irq','input_capture','sio_start','sio_retire','sio_shutdown','sio_terminal','signal_post','sio_alarm','sio_watchdog','tasks_forbid','tasks_permit')
    result={n:p['labels'][n] for n in names}
    for name,prefix in (('visible','M_BREAKPROBE_VISIBILITY_'),('usable','M_BREAKPROBE_USABLE_'),('retained','M_BREAKPROBE_COMMIT_'),('prompt_collected','M_BREAKPROBE_RETAINED_'),('allocation_cycle','M_SHELLBREAKTEST_ALLOCATECYCLE_'),('collected','M_FSOPERATION_COLLECT_')):
        result[name]=next(r['address'] for r in p['image']['routines'] if r['name'].startswith(prefix))
    result['forbid_retire_sio']=call_marker(p,'M_SIODRIVER_RETIREWORKER_','tasks_rem_task')
    result['forbid_retire_console']=call_marker(p,'M_CONSOLEDRIVER_RETIREWORKER_','tasks_rem_task')
    result['durable']=call_marker(p,'M_CONSOLEFOREGROUND_NOTIFYONE_','tasks_signal')
    result['cancel']=call_marker(p,'M_FSOPERATION_REQUEST_','tasks_signal')
    result['queued_reply']=call_marker(p,'M_FSOPERATION_PUMP_','ports_reply_msg')
    result['sector_end']=sector_end_marker(p)
    return result

def run_case(p,out,name,size,profile,trace,marks,schedule=None):
    out.mkdir(parents=True,exist_ok=True)
    for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):os.environ.pop(key,None)
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    media=out/'volume.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);digest=sha256(media)
    mode,command=CASES[name];saved={};actions=[];observations=[];origin=None
    def at(name,module='SHELLBREAKTEST'):return next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    q=at('probe');scope=0;cs=p['build']['memory']['console_storage'];ts=p['build']['task_storage'];instance=cs['INSTANCE'];sd=ts['BASE']+0x800
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest' if profile==1 else 'generic56k');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.mount(0,str(media))
        def far(address,n):
            raw=bytearray()
            for i in range(0,n,2):raw.extend((b.eval_expr(f'dw(${address+i:x})')&65535).to_bytes(2,'little'))
            return bytes(raw[:n])
        def rendezvous(condition,point='native_nmi'):
            marker=p['labels'][point];b.bp_clear_all();b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs;last=time.monotonic()
            def regs():
                nonlocal last
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Shell break stopped: checks='+str(b.peek16(at('checks')))+' status='+hex(b.peek16(adapter.STATE)))
                if time.monotonic()-last>30:print(name,'frame',b.eval_expr('@frame'),'phase',b.peek(q+9).hex(),flush=True);last=time.monotonic()
                return r
            b.regs=regs
            try:run_to(b,marker,60000,1800,condition)
            finally:b.regs=original
        def frames(n):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def key(key,state,point='native_nmi',condition=None):
            require(b._cmd_ok(f'KEY {key} {state}')['raw_scan'],'Physical key input required')
            actions.append(dict(key=key,state=state,frame=b.eval_expr('@frame')-origin))
            if point!='native_nmi':actions[-1]['point']=point
            if condition is not None:actions[-1]['condition']=condition
        def at_frame(action):
            frame=origin+action['frame'];point=action.get('point','native_nmi')
            condition=f'@frame>={frame}'
            if action.get('condition'):condition=f'({condition})&({action["condition"]})'
            # An observation can record two actions at the same stopped NMI.
            # Resuming that breakpoint again would move the second by a frame.
            if b.eval_expr('@frame')!=frame or int(b.regs()['PC'].lstrip('$'),16)!=p['labels'][point] or not b.eval_expr(condition):rendezvous(condition,point)
            require(b.eval_expr('@frame')==frame,'Replay frame changed: '+str(action)+' got '+str(b.eval_expr('@frame')-origin))
        def control(value):
            if schedule is not None:at_frame(next(a for a in schedule if a.get('control')=='finish' and a['value']==value))
            b.poke(q+11,value);actions.append(dict(control='finish',value=value,frame=b.eval_expr('@frame')-origin))
        def sample(stage):
            live=b.eval_expr(f'db(${ts["LIVE"]:x})');created=b.eval_expr(f'dw(${ts["CREATED"]:x})')
            require(live==8 and created==7,'Eight simultaneous Tasks required')
            observations.append(dict(stage=stage,frame=b.eval_expr('@frame')-origin,live=live,created=created,allocations=int.from_bytes(b.memdump(at('mix')+22,4),'little'),reader_active=b.peek(at('reader')+4)[0],sio_phase=b.eval_expr(f'db(${sd+1:x})')))
        def physical(stage):
            rendezvous(f'(db(${q+9:x})={3 if stage=="prompt" else 4})&(db(${at("visible","BREAKPROBE"):x})=1)')
            cells=int.from_bytes(far(instance,3),'little');retained=read_cells(far,instance);screen=b.memdump(saved['at'],960)
            expected=bytearray(glyphs()[v] for v in retained);cursor=int.from_bytes(far(instance+12,2),'little')*40+int.from_bytes(far(instance+10,2),'little');expected[cursor]^=128
            require(screen==expected,'Physical prompt differs from retained text/cursor')
            index=b.peek16(at('promptIndex','BREAKPROBE'));require(retained[index:index+2]==b'> ','Missing fresh prompt')
            for suffix,raw in (('cells',retained),('screen',screen)):(out/(stage+'.'+suffix+'.bin')).write_bytes(raw)
            observations.append(dict(stage=stage,frame=b.eval_expr('@frame')-origin,prompt_index=index,screen_sha256=sha256(out/(stage+'.screen.bin'))))
        def before(b):
            nonlocal origin,scope
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b.memload(at('scenario'),mode.to_bytes(2,'little'));b.memload(at('commandText'),command.encode()+bytes(1))
            b.memload(q,(70003 if size==256 else 777).to_bytes(4,'little'));b.poke(q+8,129 if size==256 else 83);b._cmd_ok('KEY ALL up')
            if trace:b.profile_start()
            rendezvous(f'db(${q+9:x})=1');origin=b.eval_expr('@frame');sample('admitted');scope=int.from_bytes(b.memdump(at('scope','BREAKPROBE'),3),'little')
            b.poke(q+10,1)
            if schedule is None:
                if mode==1:condition=f'db(${at("computing"):x})=1';point='native_nmi'
                elif mode==2:condition=f'db(${scope+21:x})=2';point='native_nmi'
                elif mode==7:
                    point='native_nmi'
                    condition=f'(db(${q+9:x})=2)&((dw(${instance+37:x})|db(${instance+39:x}))!=0)&(db(${scope+21:x})=5)'
                elif mode==4:condition=f'(db(${scope+21:x})=3)';point='native_nmi'
                else:condition=f'(db(${scope+21:x})=3)&(db(${sd+1:x})=11)&(dw(${sd+10:x})<8)';point='native_irq'
                # Distinguish the target operation from Open and redirection.
                if mode in (3,4,5,6):
                    client=int.from_bytes(far(scope+3,3),'little');action={3:82,4:24,5:8,6:82}[mode]
                    condition+=f'&(dw(${client+6+16+6:x})={action})'
                rendezvous(condition,point)
                if name=='typeahead':
                    for pressed in ('E','X','I','T','RETURN'):
                        capture=cs['CAPTURE'];head=b.eval_expr(f'db(${capture+1:x})')
                        key(pressed,'down');rendezvous(f'db(${capture+1:x})!={head}');key(pressed,'up');frames(2)
                sample('interrupted')
                if name=='ctrl-c':key('CTRL','down')
                key('C' if name=='ctrl-c' else 'BREAK','down',point,condition);actions[-1]['break_start']=True
                rendezvous(f'(db(${scope+18:x})=1)|(db(${q+9:x})=3)');key('C' if name=='ctrl-c' else 'BREAK','up')
                if name=='ctrl-c':key('CTRL','up')
                actions[-1]['break_end']=True
            else:
                for action in schedule:
                    at_frame(action);point=action.get('point','native_nmi')
                    key(action['key'],action['state'],point,action.get('condition'))
                    for field in ('break_start','break_end'):
                        if action.get(field):actions[-1][field]=True
                    if action.get('break_end'):break
            physical('prompt');sample('recovered')
            control(1)
            rendezvous(f'db(${cs["INSTANCE"]+51:x})=2')
            if schedule is None:
                for pressed in ('E','C','H','O','SPACE','O','K','RETURN'):
                    keys=b.peek16(at('keys','BREAKPROBE'));key(pressed,'down');rendezvous(f'dw(${at("keys","BREAKPROBE"):x})={keys+1}');key(pressed,'up');frames(2)
            else:
                following=False
                for action in schedule:
                    if 'control' in action:continue
                    if action.get('break_end'):following=True;continue
                    if not following:continue
                    at_frame(action);key(action['key'],action['state'])
            physical('next-command');control(2);b.bp_clear_all()
        runtime,_=execute(b,{**p,'output':out},before_run=before,timeout=1800,frame_limit=60000)
        if trace:b.profile_stop()
        require(b.peek(q+9)==bytes([5]),'Incomplete shell ownership cleanup');ownership(b,p,p['output'])
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console not restored')
        require(sha256(media)==digest,'Media changed')
        hardware=far_read(b,sd,128,out);require(hardware[0]==hardware[1]==hardware[45]==0 and hardware[12:15]==hardware[16:19]==bytes(3),'Serial ownership retained')
    result=dict(status='pass',name=name,runtime=runtime,machine=machine,observations=observations,schedule=actions,media_sha256=digest,xex_sha256=sha256(p['xex']))
    if trace:
        with (out/'emulator.log').open() as src,(out/'trace.log').open('w') as dst:
            for line in src:
                if '[SIOPOC] ' in line or '[SIOTXN] ' in line:dst.write(line)
        events=read_events(out/'trace.log');times=lambda key:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[key]]
        durable=times('durable');require(len(durable)==1,'Missing/duplicate durable break')
        capture=max(t for t in times('input_capture') if t<=durable[0]);visible=min(t for t in times('visible') if t>=durable[0]);retained=min(t for t in times('retained') if t>=durable[0])
        usable=min(t for t in times('usable') if t>=durable[0]);completed=max(visible,usable)
        result['operation_observations']={key:[t for t in times(key) if capture<=t<=completed] for key in ('cancel','queued_reply','collected','sector_end','prompt_collected')}
        result['break_timing']=dict(capture=capture,durable=durable[0],retained=retained,physical=visible,usable=usable,physical_ms=(visible-capture)/BASE_HZ*1000,ready_ms=(usable-capture)/BASE_HZ*1000,delivery_ms=(durable[0]-capture)/BASE_HZ*1000,prompt_ms=(completed-capture)/BASE_HZ*1000)
        down=next(a['frame'] for a in actions if a.get('break_start'))
        prompt=next(a['frame'] for a in observations if a['stage']=='prompt')
        result['break_timing']['keypress_to_observed_prompt_upper_ms']=(prompt-down+1)*20
        (out/'measurements.json').write_text(json.dumps(result,indent=2)+'\n')
        if mode==2:
            cancel=times('cancel');reply=times('queued_reply');require(len(cancel)==len(reply)==1,'Queued cancellation did not win')
            result['break_timing'].update(queued_publication=cancel[0],queued_reply=reply[0])
            result['break_timing']['queued_reply_ms']=(reply[0]-cancel[0])/BASE_HZ*1000
            require(0<=result['break_timing']['queued_reply_ms']<=250,'Queued reply exceeds 250 ms')
        validate_timing(result['break_timing'],queued=mode==2)
        result['serial_timing']=serial_timing(out/'trace.log',marks,media,size,0,None,key_count=None,divisor=0 if profile==1 else 8)
        require(result['serial_timing']['verdict']=='pass','Serial timing failed: '+str(result['serial_timing']['violations']))
    (out/'case.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def run(out,mode,name,size,profile,bank,replay,reuse=False):
    inputs={name:sha256(ROOT/name) for name in ('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tests/programs/shell_break.act','tests/programs/breakprobe.act','tests/programs/shell_concurrent.act','tools/test_shell_break.py','tools/shell_break_timing.py','tools/console_concurrent_trace.py')}
    out.mkdir(parents=True,exist_ok=True);observers=instrument(out,size)
    import generate_tasks
    original=generate_tasks.task_entries;entries=('MAIN','READERENTRY','PRODUCERENTRY','SIGNALENTRY','RECEIVERENTRY')
    def select(image):return original(dict(image,routines=[r for r in image['routines'] if not r['name'].startswith('M_SHELLBREAKTEST_') or any(r['name'].startswith('M_SHELLBREAKTEST_'+n+'_') for n in entries)]))
    generate_tasks.task_entries=select
    original_policy=generate_tasks.policy_modules
    def policy(*args,**kwargs):
        directory=original_policy(*args,**kwargs)
        (directory/'consoledriver.act').write_bytes((out/'consoledriver.act').read_bytes())
        return directory
    generate_tasks.policy_modules=policy
    try:p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc'),out/'shell_break.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size,profile=profile)])
    finally:
        generate_tasks.task_entries=original
        generate_tasks.policy_modules=original_policy
    require(p['build']['optimize']==(mode=='opt'),'Reused compiler mode differs')
    require(p['build']['dos_mounts']==[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size,profile=profile,boot=1,format=1)],'Reused mount configuration differs')
    require(p['build']['memory']['config']['kernel_bank']==bank,'Reused kernel bank differs')
    marks=markers(p);first=run_case(p,out/'observed',name,size,profile,True,marks)
    result=dict(status='pass',source_inputs=inputs,build=p['build'],case=first,marks=marks,observers=observers,pin=PIN,sector_bytes=size,profile=profile,bank_zero=dict(fixed_delta=0,per_task_delta=0))
    if replay:
        result['replay']=run_case(p,out/'replay',name,size,profile,False,marks,first['schedule'])
        require(result['replay']['schedule']==first['schedule'] and result['replay']['xex_sha256']==first['xex_sha256'],'Replay image/schedule changed')
    require(all(sha256(ROOT/n)==h for n,h in inputs.items()),'Qualification input changed during execution')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--scenario',choices=CASES,default='compute');a.add_argument('--size',type=int,choices=(128,256),default=256);a.add_argument('--profile',type=int,choices=(1,4),default=1);a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--reuse-build',action='store_true');a.add_argument('--replay',action='store_true');a.add_argument('--output',type=Path,required=True)
    o=a.parse_args();out=o.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(out,o.case,o.scenario,o.size,o.profile,o.bank,o.replay,o.reuse_build)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Shell break passed',o.case,o.scenario,o.size,o.profile,flush=True)
