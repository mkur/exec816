#!/usr/bin/env python3
"""Physical typing and bounded line editing alongside one real MyDOS Read."""
import adapter_state as adapter
import argparse,hashlib,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,sha256
from os_boundary import emulator,run_to
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

from generate_console import constants as console_layout
CONSOLE_LAYOUT=console_layout()

def run(t,out,optimize,size,bank=1):
    out.mkdir(parents=True,exist_ok=True)
    p=build(t,ROOT/'tests/programs/native_console_dos.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            dos_mounts=[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1)])
    p['build']['console_example_inputs']={name:sha256(ROOT/name) for name in ('examples/console.act','examples/console-session.inc','tests/programs/native_console_dos.act','tools/test_console_dos.py')}
    media=out/'volume.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);media_hash=sha256(media)
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console emulator')
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.mount(0,str(media))
        saved={};stimuli=[];observations=[]
        def at(name):
            offsets=dict(LINELENGTH=0,QUITTING=1,TYPED=2,DURINGREAD=4,LINES=6,TEXTREADS=8,ERRORS=10)
            if name in offsets:return at('EDITOR')+offsets[name]
            return next(x['address'] for x in p['image']['data'] if '_CONSOLEDOSTEST_'+name+'_' in x['name'])
        reader=at('READER');require(next(x['size'] for x in p['image']['data'] if x['address']==reader)==22,'Example reader layout changed')
        cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE'];ts=p['build']['task_storage']
        def readfar(at,n):return bytes(b.eval_expr(f'db(${at+i:x})') for i in range(n))
        def rendezvous(condition,timeout=120,frames=6000):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original();pc=int(r['PC'].lstrip('$'),16)
                if pc in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Console/DOS stopped before checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],frames,timeout,condition)
            finally:b.regs=original
        def pending():rendezvous(f'(db(${cs["INSTANCE"]+51:x})=2)&((dw(${instance+34:x})!=0)|(db(${instance+36:x})!=0))')
        def key(name):
            pending();prior=b.peek16(at('TYPED'));active=b.peek(reader+4)[0]
            require(b._cmd_ok(f'KEY {name} down')['raw_scan'],'Not physical input')
            start=b.eval_expr('@frame');rendezvous(f'dw(${at("TYPED"):x})={prior+1}')
            end=b.eval_expr('@frame');b._cmd_ok(f'KEY {name} up');rendezvous(f'@frame>={end+4}')
            stimuli.append(dict(key=name,start_frame=start,consumed_frame=end,during_read=bool(active)))
            if name!='X' or (prior+1)%8==0:print('Input',name,'consumed',prior+1,'during read',bool(active),flush=True)
        def screen(label):
            pending();rendezvous(f'db(${instance+CONSOLE_LAYOUT["INSTANCE_DIRTYROWS"]:x})=0')
            cells=int.from_bytes(readfar(instance,3),'little');raw=readfar(cells,960);physical=b.memdump(saved['at'],960)
            (out/(label+'.cells.bin')).write_bytes(raw);(out/(label+'.screen.bin')).write_bytes(physical)
            (out/(label+'.png')).write_bytes(b.screenshot())
            observations.append(dict(stage=label,live=b.eval_expr(f'db(${ts["LIVE"]:x})'),created=b.eval_expr(f'dw(${ts["CREATED"]:x})'),cells_sha256=sha256(out/(label+'.cells.bin')),screen_sha256=sha256(out/(label+'.screen.bin'))))
            return raw
        def before(b):
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
            expected=777 if size==128 else 70003
            for i,v in enumerate(expected.to_bytes(4,'little')):b.poke(at('EXPECTEDBYTES')+i,v)
            b.poke(at('SEED'),83 if size==128 else 129)
            if size==256:
                path=next(x for x in p['image']['data'] if '_READPATH_' in x['name'] and x['size']>3)
                for i,v in enumerate(b'D1:LARGE.BIN\0'):b.poke(path['address']+i,v)
            b._cmd_ok('KEY ALL up')
            rendezvous(f'db(${at("CHECKPOINT"):x})=1');pending()
            observations.append(dict(stage='console-open',live=b.eval_expr(f'db(${ts["LIVE"]:x})'),created=b.eval_expr(f'dw(${ts["CREATED"]:x})')))
            key('BACKSPACE')
            key('R');key('RETURN');rendezvous(f'db(${reader+4:x})=1')
            observations.append(dict(stage='first-read',live=b.eval_expr(f'db(${ts["LIVE"]:x})'),created=b.eval_expr(f'dw(${ts["CREATED"]:x})')))
            for name in ('A','B','BACKSPACE','C','RETURN'):key(name)
            rendezvous(f'(dw(${reader+8:x})=1)&(db(${reader+3:x})=0)',1800,30000)
            raw=screen('echo');require(b'> ac' in raw,'Backspace/echo result missing')
            # Real presses saturate the application line limit; excess input
            # is ignored and one BS remains on the current physical row.
            for _ in range(38):key('X')
            pending();require(b.peek(at('LINELENGTH'))==bytes([36]),'Line limit not enforced')
            require(b.eval_expr(f'dw(${instance+10:x})')==38,'Bounded edit wrapped')
            key('BACKSPACE');pending();require(b.peek(at('LINELENGTH'))==bytes([35]),'Bounded backspace failed')
            key('RETURN')
            for name in ('T','RETURN','E','RETURN','T','RETURN'):key(name)
            raw=screen('files');require(b'File error' in raw,'Ordinary DOS error did not remain visible')
            buffer=int.from_bytes(b.memdump(at('TEXTBUFFER'),3),'little')
            expected=bytes(10 if (i&255)^34==155 else ((i&255)^34) if 32<=((i&255)^34)<=126 else 46 for i in range(259))
            require(readfar(buffer,259)==expected,'ATASCII preview conversion mismatch')
            observations[-1]['atascii_preview_sha256']=hashlib.sha256(expected).hexdigest()
            require(observations[1]['live']==5 and observations[1]['created']==4,'Missing first-open worker set')
            require(observations[-1]['live']==5 and observations[-1]['created']==4,'Task created per file/console operation')
            key('Q');key('RETURN');rendezvous(f'db(${at("CHECKPOINT"):x})=2',1800,30000)
            b.poke(at('GATE'),1);b.bp_clear_all()
        try:rt,_=execute(b,p,before_run=before,timeout=1800,frame_limit=30000)
        except Exception:
            print('Native status',b.memdump(adapter.STATE,64).hex(),flush=True)
            for index,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{index}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            print('Console/DOS counters',{name:b.memdump(at(name),22 if name=='READER' else 2).hex() for name in ('CHECKPOINT','TYPED','DURINGREAD','TEXTREADS','ERRORS','READER')},flush=True);raise
        require(data(b,p['image'],'checkpoint')==[3],'Missing cleanup checkpoint')
        require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Console not restored')
        ownership(b,p,out);require(sha256(media)==media_hash,'Media changed')
        counters={name:int.from_bytes(b.memdump(at(name.upper()),4 if name=='verified' else 2),'little') for name in ('typed','duringRead','lines','textReads','errors','verified')}
    return dict(status='pass',build=p['build'],runtime=rt,machine=machine,sector_bytes=size,media_sha256=media_hash,stimuli=stimuli,observations=observations,counters=counters,limits=dict(checkpoint_host_seconds=120,checkpoint_guest_frames=6000,read_host_seconds=1800,read_guest_frames=30000))
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--sector-size',type=int,choices=(128,256),required=True);a.add_argument('--bank',type=int,default=1);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.sector_size,args.bank)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console DOS passed',args.case,args.sector_size,flush=True)
