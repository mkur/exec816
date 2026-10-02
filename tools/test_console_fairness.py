#!/usr/bin/env python3
"""Bounded eight-Task multiwindow/SIO development workload with passive timing."""
import adapter_state as adapter
import argparse,hashlib,json,os,shutil
from pathlib import Path
from generate_console import constants as console_constants
from native_program import ROOT,build,compiler,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import glyph
from dos_concurrent_trace import call_marker,sector_end_marker
from console_concurrent_trace import analyze as wire_timing
from sio_transaction_trace import read_events,BASE_HZ
from sio_concurrent_trace import LIMITS as SIO_LIMITS
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
LIMITS=dict(small_collected_ms=250,small_visible_ms=500,flood_collected_ms=1000,third_collected_ms=250,third_visible_ms=500,cooked_echo_ms=500,break_durable_ms=100)

def timing(path,marks,media):
    wire=wire_timing(path,marks,media,128,0,None,key_count=None)
    require(wire['verdict']=='pass','SIO timing: '+str(wire['violations']))
    events=read_events(path)
    def times(name):return [t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
    def bounded(name,starts,ends):
        require(len(starts)==len(ends) and starts,name+' missing observations')
        values=[(b-a)/BASE_HZ*1000 for a,b in zip(starts,ends)]
        require(all(0<=v<=LIMITS[name] for v in values),name+' exceeded: '+str(values))
        return dict(samples=len(values),max_ms=max(values),limit_ms=LIMITS[name])
    capture=times('input_capture');require(len(capture)==4,'Expected Z, A, Return, BREAK captures')
    result={}
    for name,end in [('small_collected_ms','small_collected'),('small_visible_ms','small_visible')]:result[name]=bounded(name,times('small_begin'),times(end))
    require(len(times('small_begin'))==8 and len(times('flood_begin'))>=16,'Missing per-window progress')
    require(times('small_begin')[0]>=times('flood_collected')[11],'Small writes preceded scrolling')
    result['flood_collected_ms']=bounded('flood_collected_ms',times('flood_begin'),times('flood_collected'))
    for name,start,end in [('third_collected_ms',capture[:1],'third_collected'),('third_visible_ms',capture[:1],'third_visible'),('cooked_echo_ms',capture[1:2],'echo_visible'),('break_durable_ms',capture[3:],'break_durable')]:result[name]=bounded(name,start,times(end))
    begins,ends=times('read_begin'),times('read_end');require(len(begins)==len(ends) and begins,'Missing complete file reads')
    starts,posts=times('sio_start'),times('signal_post');gaps=[]
    for begin,end in zip(begins,ends):
        gaps += [(b-a)/BASE_HZ*1e6 for a,b in zip(posts,starts[1:]) if begin<=a<=b<=end]
    require(gaps and max(gaps)<=SIO_LIMITS['next_start_max_us'],'SIO next-sector deadline')
    require(any(begin<capture[0]<end for begin,end in zip(begins,ends)),'Keyboard did not overlap DOS.Read')
    result['next_sector_max_us']=max(gaps)
    return dict(windows=result,wire=wire)

def run(out,mode,from_build=None):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_fairness.act'
    console=console_constants()
    p=read_build(from_build) if from_build else build(compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)])
    require(p['build']['optimize']==(mode=='opt'),'Reused build mode differs')
    def routine(prefix):
        matches=[r['address'] for r in p['image']['routines'] if r['name'].startswith(prefix)]
        require(len(matches)==1,'Ambiguous marker '+prefix);return matches[0]
    def at(name):return next(x['address'] for x in p['image']['data'] if '_WINDOWFAIR_'+name.upper()+'_' in x['name'])
    marks={n:p['labels'][n] for n in ('native_irq','native_nmi','sio_start','sio_retire','sio_shutdown','signal_post','sio_alarm','sio_watchdog','input_capture','tasks_forbid','tasks_permit')}
    for name,r in dict(small_begin='SmallBegin',small_collected='SmallCollected',small_visible='SmallVisible',flood_begin='FloodBegin',flood_collected='FloodCollected',third_collected='ThirdCollected',third_visible='ThirdVisible',echo_visible='EchoVisible',read_begin='FileBegin',read_end='FileCollected').items():marks[name]=routine('M_WINDOWFAIR_'+r.upper()+'_')
    marks['sector_end']=sector_end_marker(p)
    marks['forbid_retire_sio']=call_marker(p,'M_SIODRIVER_RETIREWORKER_','tasks_rem_task')
    marks['forbid_retire_console']=call_marker(p,'M_CONSOLEDRIVER_RETIREWORKER_','tasks_rem_task')
    marks['break_durable']=call_marker(p,'M_CONSOLEFOREGROUND_NOTIFYONE_','tasks_signal')
    for name in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):os.environ.pop(name,None)
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);media_hash=sha256(media)
    saved={};observed=[]
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest');b.mount(0,str(media));machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        ts=p['build']['task_storage'];cs=p['build']['memory']['console_storage']
        def rendezvous(condition,point='native_nmi'):
            b.bp_clear_all();b.bp_set(p['labels'][point],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Fairness fixture stopped early')
                return r
            b.regs=regs
            try:run_to(b,p['labels'][point],9000,180,condition)
            finally:b.regs=original
        def frames(n):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def press(key):
            old=b.eval_expr(f'dw(${cs["CAPTURE"]+10:x})')
            require(b._cmd_ok(f'KEY {key} down')['raw_scan'],'Physical key input required')
            rendezvous(f'dw(${cs["CAPTURE"]+10:x})>{old}')
            b._cmd_ok(f'KEY {key} up');frames(2)
        def before(b):
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up');b.profile_start()
            for stage in range(1,6):
                rendezvous(f'db(${at("phase"):x})={stage}')
                if stage<5:
                    live=b.eval_expr(f'db(${ts["LIVE"]:x})');contexts=[b.eval_expr(f'db(${ts["BASE"]+i*ts["SIZE"]+ts["TCB_STATE"]:x})') for i in range(8)]
                    require(live==8 and all(contexts),'Eight simultaneous live Tasks required')
                    observed.append(dict(stage=stage,live=live,contexts=contexts,frame=b.eval_expr('@frame')))
                if stage==2:
                    sd=ts['BASE']+0x800
                    rendezvous(f'(db(${sd+1:x})=11)&(dw(${sd+10:x})<8)',point='native_irq');press('Z')
                if stage==3:press('A');press('RETURN')
                if stage==4:press('BREAK')
                if stage==5:
                    physical=b.memdump(saved['at'],960);oracle=bytearray(960);tiles=[]
                    for name,left,top,w,h in [('first',0,0,20,12),('second',20,0,20,12),('third',0,12,40,12)]:
                        unit=int.from_bytes(b.memdump(at(name),4),'little');entry=cs['WINDOWS']+console['WINDOWS_ITEMS']+(unit&3)*console['WINDOW_SIZE']
                        raw=bytes(b.eval_expr(f'db(${entry+8+i:x})') for i in range(3));instance=int.from_bytes(raw,'little')
                        raw=bytes(b.eval_expr(f'db(${instance+i:x})') for i in range(3));base=int.from_bytes(raw,'little');cells=bytes(b.eval_expr(f'db(${base+i:x})') for i in range(w*h))
                        for row in range(h):oracle[(top+row)*40+left:(top+row)*40+left+w]=bytes(map(glyph,cells[row*w:(row+1)*w]))
                        tiles.append(cells)
                    require(tiles[0]==b'#'*220+b' '*20,'Flood retained order/scroll contents')
                    require(tiles[1]==b'12345678'*8+b' a'+b' '*174,'Small/CON byte order')
                    require(tiles[2]==b'z'+b' '*479,'Unfocused/read byte isolation')
                    oracle[481]^=128;require(physical==oracle,'Exact final physical tiles/cursor')
                    saved['route_peak']=b.eval_expr(f'db(${cs["ROUTES"]+4:x})');require(saved['route_peak']<=16,'Route capacity')
                    saved['screen_sha256']=hashlib.sha256(physical).hexdigest()
                print('Fairness checkpoint',stage,'floods',b.peek16(at('floods')),'reads',b.peek16(at('reads')),flush=True)
                b.poke(at('gate'),1)
            b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=15000)
        except Exception:
            print('Fairness phase/checks/status',data(b,p['image'],'phase'),data(b,p['image'],'checks',True),hex(b.peek16(adapter.STATE)),flush=True);raise
        b.profile_stop();require(runtime['created']==7,'Unexpected Task creation')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console ownership restoration')
        ownership(b,p,p['output']);require(sha256(media)==media_hash,'Media changed')
        counters={n:data(b,p['image'],n,True)[0] for n in ('checks','floods','smalls','reads','computes')}
    with (out/'emulator.log').open() as src,(out/'trace.log').open('w') as dst:
        for line in src:
            if '[SIOPOC] ' in line or '[SIOTXN] ' in line:dst.write(line)
    measured=timing(out/'trace.log',marks,media)
    return dict(status='pass',tier='development',mode=mode,build=p['build'],pin=PIN,machine=machine,runtime=runtime,counters=counters,observations=observed,limits=LIMITS,timing=measured,route_peak=saved['route_peak'],screen_sha256=saved['screen_sha256'],media_sha256=media_hash,marks=marks,source_inputs={str(source.relative_to(ROOT)):sha256(source),'tools/test_console_fairness.py':sha256(ROOT/'tools/test_console_fairness.py')})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--from-build',type=Path);args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.from_build)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Window fairness development checks passed',args.case,flush=True)
