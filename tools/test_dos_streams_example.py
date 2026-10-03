#!/usr/bin/env python3
"""Resident DOS streams: physical input, background 70003-byte Read, redirection."""
import adapter_state as adapter
import argparse,json,shutil,time
from console_model import read_cells
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import terminal
from os_boundary import emulator,run_to
LIMITS=dict(checkpoint_host_seconds=240,checkpoint_guest_frames=12000,completion_host_seconds=1800,completion_guest_frames=30000)


from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def run(t,out,mode,nil=False):
    out.mkdir(parents=True,exist_ok=True)
    p=build(t,ROOT/('examples/dos-nil.act' if nil else 'tests/programs/dos_streams_example.act'),out,
        optimize=mode=='opt',tasks=True,task_capacity=8,console=not nil,
        dos_mounts=[] if nil else [dict(alias='D1',unit=49,sectors=2000,sector_bytes=256,profile=1)])
    media=out/'volume.atr'
    if not nil:shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-256.atr',media)
    digest=sha256(media) if not nil else None
    def at(name):return next(d['address'] for d in p['image']['data'] if ('_DOSNILEXAMPLE_' if nil else '_DOSSTREAMSEXAMPLE_')+name.upper()+'_' in d['name'])
    schedule=[];observations=[];counts={}
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        if not nil:b.config('diskemu','fastest');b.mount(0,str(media))
        saved={}
        def far(addr,n):return bytes(b.eval_expr(f'db(${addr+i:x})') for i in range(n))
        def rendezvous(condition,long=False):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs;last=time.monotonic()
            def regs():
                nonlocal last
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Example stopped before checkpoint')
                if time.monotonic()-last>30:
                    print('Example progress',b.peek(at('phase')),'reader',b.memdump(at('reader'),22).hex(),flush=True);last=time.monotonic()
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],LIMITS['completion_guest_frames' if long else 'checkpoint_guest_frames'],LIMITS['completion_host_seconds' if long else 'checkpoint_host_seconds'],condition)
            finally:b.regs=original
        def snapshot(stage):
            ts=p['build']['task_storage'];created=b.eval_expr(f'dw(${ts["CREATED"]:x})');live=b.eval_expr(f'db(${ts["LIVE"]:x})')
            require(created==4 and live==5,'Resident example needs exactly five live Tasks')
            observations.append(dict(stage=stage,created=created,live=live,frame=b.eval_expr('@frame'),reader=b.memdump(at('reader'),22).hex()))
        def key(name,state):
            require(b._cmd_ok(f'KEY {name} {state}')['raw_scan'],'Not physical keyboard input')
            schedule.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def check_screen(payload,stage):
            cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE']
            expected,physical,cursor=terminal(payload)
            rendezvous(f'(db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0)&(dw(${cs["PRESENTATION"]+10:x})={cursor})')
            cells=int.from_bytes(far(instance,3),'little')
            require(read_cells(far,instance)==expected,'Example terminal contents differ')
            require(b.memdump(saved['at'],960)==physical,'Example physical screen differs')
            (out/(stage+'.cells.bin')).write_bytes(expected);(out/(stage+'.screen.bin')).write_bytes(physical)
            observations.append(dict(stage=stage,cells_sha256=sha256(out/(stage+'.cells.bin')),screen_sha256=sha256(out/(stage+'.screen.bin'))))
        def before(b):
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
            if nil:return
            b._cmd_ok('KEY ALL up');rendezvous(f'db(${at("phase"):x})=1');snapshot('ready-with-restored-defaults');b.poke(at('gate'),1)
            cs=p['build']['memory']['console_storage']
            rendezvous(f'(db(${at("phase"):x})=2)&(db(${at("reader")+4:x})=1)&(db(${cs["INSTANCE"]+51:x})=2)')
            snapshot('keyboard-wait-overlaps-file-read');key('A','down');rendezvous(f'dw(${at("typed"):x})=1');key('A','up')
            rendezvous(f'(db(${at("reader")+3:x})=1)&(db(${cs["INSTANCE"]+51:x})=2)',long=True)
            snapshot('disk-completed-while-parent-still-waits')
            check_screen(b'\x0cDOS STREAMS\na\nDISK DONE\n','disk-message-before-next-key')
            key('Q','down');rendezvous(f'db(${at("phase"):x})=4',long=True);key('Q','up')
            counts.update({n:int.from_bytes(bytes(data(b,p['image'],n)),'little') for n in ('typed','duringRead','redirected','verified')})
            require(counts==dict(typed=2,duringRead=1,redirected=2,verified=70003),'Incomplete stream example')
            check_screen(b'\x0cDOS STREAMS\na\nDISK DONE\nq','final-display')
            b.poke(at('gate'),1);b.bp_clear_all()
        try:rt,_=execute(b,p,before_run=before,timeout=LIMITS['completion_host_seconds'],frame_limit=LIMITS['completion_guest_frames'])
        except Exception:
            if not nil:print('Example failure phase',data(b,p['image'],'phase'),'reader',data(b,p['image'],'reader'),'commandError',data(b,p['image'],'commandError'),flush=True)
            raise
        if nil:
            counts['checks']=int.from_bytes(bytes(data(b,p['image'],'checks')),'little');require(counts['checks']==6 and rt['created']==0,'NIL example created a worker')
        else:require(data(b,p['image'],'phase')==[5],'Example cleanup not reached')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Example did not restore console state')
        ownership(b,p,out)
        if not nil:require(sha256(media)==digest,'Read-only media changed')
    return dict(status='pass',mode=mode,nil=nil,build=p['build'],runtime=rt,machine=machine,limits=LIMITS,
        observations=observations,schedule=schedule,counts=counts,media_sha256=digest,
        source_inputs={s:sha256(ROOT/s) for s in ('examples/dos-streams.act','examples/dos-streams-session.inc','examples/dos-nil.act','tests/programs/dos_streams_example.act','tools/test_dos_streams_example.py')})

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--nil',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(args.compiler_dir),out,args.case,args.nil)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS streams example passed',args.case,'NIL' if args.nil else 'RAW',flush=True)
