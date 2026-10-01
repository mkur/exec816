#!/usr/bin/env python3
"""Cancel queued filesystem packets while a 70,003-byte peer Read continues."""
import adapter_state as adapter
from library_paths import library_file, read_source
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,optimize,bank,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-256.atr',media);media_sha=sha256(media)
    (out/'filesystem_cancel.act').write_bytes((ROOT/'tests/programs'/('filesystem_cancel_reuse.act' if reuse else 'filesystem_cancel.act')).read_bytes())
    (out/'fscancelprobe.act').write_bytes((ROOT/'tests/programs/fscancelprobe.act').read_bytes())
    for name in ('dosclient.act','fshandler.act'):
        source=read_source(library_file(name)).replace('USE EXEC','USE EXEC\nUSE FSCANCELPROBE',1)
        if name=='dosclient.act':source=source.replace('EXEC.PutMsg(handler,@client.packet.sp_Msg)\n  EXEC.Permit()','EXEC.PutMsg(handler,@client.packet.sp_Msg) EXEC.Permit()\n  FSCANCELPROBE.Submitted(scope)')
        else:source=source.replace('      EXEC.Forbid()\n      message=EXEC.GetMsg(mount.port)','      FSCANCELPROBE.BeforeTake()\n      EXEC.Forbid() message=EXEC.GetMsg(mount.port)')
        (out/name).write_text(source)
    p=build(compiler(ROOT/'build/actionc'),out/'filesystem_cancel.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            dos_mounts=[dict(alias='D1',unit=49,sectors=2000,sector_bytes=256,profile=1)])
    def at(name,module='FILESYSTEMCANCELTEST'):return next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    events=[];samples=[];saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def far(a,n):return bytes(b.eval_expr(f'db(${a+i:x})') for i in range(n))
        def pointer(a):return int.from_bytes(far(a,3),'little')
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    if b.peek16(adapter.STATE)!=0xffff:print('Failure state',{n:far(at(n),32 if n in ('results','errors') else 4).hex() for n in (('phase','done','round','results','errors') if reuse else ('phase','bigDone','orderedDone','orderCount','order','orderedBytes','results','errors'))},flush=True)
                    require(b.peek16(adapter.STATE)==0xffff,'Filesystem cancel stopped: '+hex(b.peek16(adapter.STATE))+' checks='+str(b.peek16(at('checks'))))
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],60000,1200,condition)
            finally:b.regs=original
        def phase(n):
            rendezvous(f'db(${at("phase"):x})={n}')
            print('Filesystem cancel phase',n,'checks',b.peek16(at('checks')),flush=True)
        def key(state):
            require(b._cmd_ok(f'KEY BREAK {state}')['raw_scan'],'Physical BREAK required')
            events.append(dict(key='BREAK',state=state,frame=b.eval_expr('@frame')))
        def before(b):
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up')
            if reuse:
                for n in (1,2):
                    phase(n);scope=pointer(at('scope'))
                    rendezvous(f'db(${at("stage","FSCANCELPROBE"):x})=1')
                    require(far(scope+21,1)==b'\x02' and far(scope+18,1)==b'\x00','Reused client inherited completion/break')
                    key('down');rendezvous(f'db(${scope+23:x})=1');key('up')
                    b.poke(at('gate','FSCANCELPROBE'),1)
                phase(3);b.bp_clear_all();return
            for n in (1,2,3):
                phase(n);scope=pointer(at('scope'));b.poke(at('gate'),1)
                rendezvous(f'db(${scope+21:x})=2')
                require(far(at('bigDone'),1)==bytes(1),'Large Read finished before cancellation')
                key('down');start=b.eval_expr('@frame');phase(n+1);end=b.eval_expr('@frame');key('up')
                require(far(at('bigDone'),1)==bytes(1),'Queued cancellation did not beat large Read')
                samples.append(dict(operation=('Read','Open','Lock')[n-1],break_frame=start,returned_frame=end,upper_ms=(end-start+1)*20))
                rendezvous(f'@frame>={end+2}')
            b.poke(at('gate'),1)
            for number,state in ((6,2),(7,4)):
                phase(number);b.poke(at('gate'),1)
                rendezvous(f'db(${at("stage","FSCANCELPROBE"):x})=1')
                rendezvous(f'db(${scope+21:x})={state}')
                key('down')
                if number==6:rendezvous(f'db(${scope+23:x})=1')
                else:rendezvous(f'db(${scope+18:x})=1')
                key('up');b.poke(at('gate','FSCANCELPROBE'),1)
            phase(5);b.bp_clear_all()
        runtime,_=execute(b,p,before_run=before,timeout=1800,frame_limit=90000)
        ownership(b,p,out)
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console not restored')
        require(sha256(media)==media_sha,'Read-only media changed')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,pin=PIN,checks=data(b,p['image'],'checks',True),reuse=reuse,
                    results=data(b,p['image'],'results'),errors=data(b,p['image'],'errors'),events=events,samples=samples,media_sha256=media_sha,observers={n:sha256(out/n) for n in ('dosclient.act','fshandler.act','fscancelprobe.act')},
                    bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--reuse',action='store_true');a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.case=='opt',args.bank,args.reuse)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Filesystem queued cancellation passed',args.case,args.bank,flush=True)
