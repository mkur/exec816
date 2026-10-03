#!/usr/bin/env python3
"""Public RAW streams: physical keys, shared endpoint, rollback and large output."""
import adapter_state as adapter
import argparse,hashlib,json,shutil,time
from pathlib import Path
from console_model import read_cells
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import terminal
from os_boundary import emulator,run_to


from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def run(t,out,mode,bank=1):
    out.mkdir(parents=True,exist_ok=True)
    names=bytearray(520)
    for offset,value in ((0,b'RAW:'),(32,b'NIL:'),(64,b'console.device'),(96,b'CHILD\n'),
                         (128,b'ALIVE\n'),(160,b'PACKET\nRAW\n!'),(192,b'D1:TOOLS/SUB/DATA.BIN')):
        names[offset:offset+len(value)]=value
    p=build(t,ROOT/'tests/programs/dos_streams_raw.act',out,optimize=mode=='opt',tasks=True,
            task_capacity=8,console=True,kernel_bank=bank,dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],
            image_data=[(0xd1000,bytes(names)),(0xdfffe,bytes(4))])
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);digest=sha256(media)
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    def at(name):return next(x['address'] for x in p['image']['data'] if '_DOSRAWTEST_'+name.upper()+'_' in x['name'])
    observations=[];schedule=[];saved={}
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE'];ts=p['build']['task_storage']
        def readfar(addr,n):return bytes(b.eval_expr(f'db(${addr+i:x})') for i in range(n))
        def rendezvous(condition,seconds=240,frames=12000):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs;last_report=time.monotonic()
            def regs():
                nonlocal last_report
                r=original()
                if time.monotonic()-last_report>15:
                    request=int.from_bytes(readfar(instance+37,3),'little')
                    actual=int.from_bytes(readfar(request+26,4),'little') if request else None
                    print('RAW progress',b.peek16(at('checks')),actual,'frame',b.eval_expr('@frame'),flush=True)
                    last_report=time.monotonic()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'RAW stopped before checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],frames,seconds,condition)
            finally:b.regs=original
        def phase(n):
            rendezvous(f'db(${at("phase"):x})={n}');print('RAW checkpoint',n,flush=True)
        def key(name,state):
            result=b._cmd_ok(f'KEY {name} {state}')
            require(result['raw_scan'],'Cooked key event')
            schedule.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def pauseframes():rendezvous(f'@frame>={b.eval_expr("@frame")+4}')
        def cells():
            return read_cells(readfar,instance)
        def state(label):
            ds=p['build']['memory']['dos_storage']
            raw=readfar(ds['STREAMS'],16);ep=int.from_bytes(raw[1:4],'little')
            observations.append(dict(stage=label,registry=raw.hex(),endpoint=readfar(ep,98).hex() if ep else None,
                created=b.eval_expr(f'dw(${ts["CREATED"]:x})'),live=b.eval_expr(f'db(${ts["LIVE"]:x})')))
        def before(b):
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up')
            phase(1);state('first-open');key('B','down');pauseframes();key('B','up');pauseframes()
            rendezvous(f'dw(${instance+30:x})=1');b.poke(at('gate'),1)
            phase(2);require(cells()==b' '*960,'RAW input echoed automatically');state('short-read-no-echo');b.poke(at('gate'),1)
            phase(3);require(b.peek(at('readStage'))==b'\1','Reader not pending')
            require(cells().startswith(b'ALIVE'),'Other client write blocked by reader');state('pending-read-concurrent-write')
            key('A','down');pauseframes();key('A','up');pauseframes()
            phase(4);require(cells().startswith(b'ALIVE'+b' '*35+b'CHILD'),'Surviving child cannot write')
            require(97 not in cells(),'RAW short read echoed automatically');state('first-opener-released');b.poke(at('gate'),1)
            rendezvous(f'(db(${at("readStage"):x})=2)&(db(${cs["INSTANCE"]+51:x})=2)')
            key('CTRL','down');key('C','down');pauseframes();key('C','up');key('CTRL','up');pauseframes()
            rendezvous(f'(db(${at("readStage"):x})=3)&(db(${cs["INSTANCE"]+51:x})=2)')
            key('BREAK','down');pauseframes();key('BREAK','up')
            phase(5);state('large-write-collected-source-freed')
            payload=bytearray(70003)
            for j,i in enumerate(range(1,69998,32)):payload[i]=65+j%26
            payload[0]=12;payload[65535:65537]=b'XY';payload[-5:]=bytes([8,9,13,10,90])
            expected,screen,cursor=terminal(payload)
            require(cells()==expected,'70003-byte retained terminal oracle failed')
            rendezvous(f'(db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0)&(dw(${cs["PRESENTATION"]+10:x})={cursor})')
            require(b.memdump(saved['at'],960)==screen,'Eventual physical screen differs')
            (out/'large.cells.bin').write_bytes(expected);(out/'large.screen.bin').write_bytes(screen)
            observations[-1].update(payload_length=70003,payload_sha256=hashlib.sha256(payload).hexdigest(),cells_sha256=sha256(out/'large.cells.bin'),screen_sha256=sha256(out/'large.screen.bin'))
            b.poke(at('gate'),1);b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=30000)
        except Exception:
            request=int.from_bytes(readfar(instance+37,3),'little')
            (out/'failure-device.json').write_text(json.dumps(dict(instance=readfar(instance,62).hex(),request=readfar(request,42).hex() if request else None),indent=2)+'\n')
            print('RAW checks',data(b,p['image'],'checks',True),'child',data(b,p['image'],'otherChecks',True),'phase',data(b,p['image'],'phase'),'status',b.peek16(adapter.STATE),flush=True);raise
        require(data(b,p['image'],'phase')==[6],'Missing RAW completion')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'Console ownership not restored')
        ownership(b,p,out);require(sha256(media)==digest,'Read-only media changed')
        checks={n:int.from_bytes(bytes(data(b,p['image'],n)),'little') for n in ('checks','otherChecks')}
        require(checks==dict(checks=51,otherChecks=8),'Missing RAW assertions: '+str(checks))
    return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,observations=observations,checks=checks,schedule=schedule,media_sha256=digest,limits=dict(checkpoint_host_seconds=240,checkpoint_guest_frames=12000,completion_host_seconds=600,completion_guest_frames=30000))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(compiler(args.compiler_dir),out,args.case,args.bank)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DOS RAW passed',args.case,args.bank,flush=True)
