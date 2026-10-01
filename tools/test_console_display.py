#!/usr/bin/env python3
"""Native retained-screen rendering, hidden output and borrowed-screen restore."""
import adapter_state as adapter
import argparse,json,hashlib
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from test_dos_stack import execute,ownership
from test_console_coexistence import PIN
from os_boundary import emulator,run_to
from test_cooperative import data

def glyph(value):
    if 32<=value<=95:return value-32
    if 97<=value<=122 or value==124:return value
    return 31

def terminal(payload):
    cells=bytearray(b' '*960);row=col=0
    def newline():
        nonlocal row,col,cells
        col=0
        if row<23:row+=1
        else:cells[:920]=cells[40:];cells[920:]=b' '*40
    for value in payload:
        if value==12:cells[:]=b' '*960;row=col=0
        elif value==10:newline()
        elif value==13:col=0
        elif value==8:col=max(0,col-1)
        elif value==9:
            col=(col//8+1)*8
            if col>=40:newline()
        elif value>=32 and value!=127:
            cells[row*40+col]=value if value<128 else 63;col+=1
            if col==40:newline()
    screen=bytearray(map(glyph,cells));screen[row*40+col]^=128
    return cells,screen,row*40+col

def run(t,out,optimize,bank,paced=False):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if paced else PIN
    bridge=ROOT/'build/shell-paced-bridge' if paced else ROOT/'build/console-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned console emulator')
    out.mkdir(parents=True,exist_ok=True)
    p=build(t,ROOT/'tests/programs/native_console_display.act',out,optimize=optimize,tasks=True,task_capacity=8,kernel_bank=bank,console_test=True)
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        saved={};observations=[]
        def address(name):return next(d['address'] for d in p['image']['data'] if '_NATIVECONSOLEDISPLAY_'+name+'_' in d['name'])
        def readfar(at,size):return bytes(b.eval_expr(f'db(${at+i:x})') for i in range(size))
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original();pc=int(r['PC'].lstrip('$'),16)
                if pc in (p['labels']['done'],p['labels']['done']+2):require(b.peek16(adapter.STATE)==0xffff,'Console failed before display checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],3000,60,condition)
            finally:b.regs=original
        def before(b):
            screen=b.peek16(88);saved.update(screen=screen,bytes=b.memdump(screen,960),editor=b.memdump(82,16),cursor=b.peek(752)[0],display_list=b.memdump(b.peek16(560),32),font=hashlib.sha256(b.memdump(0xe000,1024)).hexdigest(),antic=b.antic(),gtia=b.gtia())
            require(all(saved['antic'][key]==value for key,value in {'DMACTL':'$22','CHACTL':'$02','CHBASE':'$e0'}.items()),'Unsupported physical display registers')
            require(saved['gtia']['PRIOR']=='$00','Unsupported physical priority')
            require(all(int(saved['gtia']['COLPF'+str(i)].lstrip('$'),16)==(b.peek(708+i)[0]&254) for i in range(4)),'Color hardware/shadow disagreement')
            b._cmd_ok('KEY ALL up')
            sequences=[b'Exec816 native console\n'+bytes(range(32,127)),bytes([12])+b''.join(bytes([65+row%26])*40 for row in range(30))+bytes([69,78,68,8,33,9,84,13,90,10])]
            first=terminal(sequences[0]);last=terminal(sequences[1])
            for stage in range(1,5):
                rendezvous(f'db(${address("STAGE"):x})={stage}')
                print('Screen checkpoint',stage,flush=True)
                physical=b.memdump(screen,960)
                require(physical==bytes(first[1] if stage<4 else last[1]),f'Physical screen oracle failed at {stage}')
                pointer=int.from_bytes(b.memdump(address('INSTANCE'),3),'little')
                cells=b.eval_expr(f'dw(${pointer:x})')|(b.eval_expr(f'db(${pointer+2:x})')<<16)
                retained=readfar(cells,960)
                require(retained==bytes(first[0] if stage<3 else last[0]),f'Retained cells failed at {stage}')
                observations.append(dict(stage=stage,screen_sha256=hashlib.sha256(physical).hexdigest(),cells_sha256=hashlib.sha256(retained).hexdigest()))
                (out/f'stage{stage}.screen.bin').write_bytes(physical)
                if stage in (1,4):
                    rendezvous(f'@frame>={b.eval_expr("@frame")+2}')
                    (out/f'stage{stage}.png').write_bytes(b.screenshot())
                if stage==2:
                    b.poke(address('GATE'),1)
                    rendezvous(f'(dw(${pointer+37:x})!=0)|(db(${pointer+39:x})!=0)')
                    observations[-1]['physical_key_during_active_write']=True
                    b._cmd_ok('KEY A down')
                    rendezvous(f'@frame>={b.eval_expr("@frame")+4}')
                    b._cmd_ok('KEY A up')
                if stage!=2:b.poke(address('GATE'),1)
            b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('Display checks/phase/stage/gate',data(b,p['image'],'checks',True),data(b,p['image'],'phase'),data(b,p['image'],'stage'),data(b,p['image'],'gate'),flush=True)
            pointer=int.from_bytes(b.memdump(address('INSTANCE'),3),'little')
            raw=readfar(pointer,62)
            print('Instance state',raw.hex(),flush=True)
            request=int.from_bytes(raw[37:40],'little')
            if request:print('Active request',readfar(request,42).hex(),flush=True)
            raise
        require(b.memdump(saved['screen'],960)==saved['bytes'],'Borrowed screen not restored')
        require(b.memdump(82,16)==saved['editor'] and b.peek(752)[0]==saved['cursor'],'Editor state not restored')
        require(b.memdump(b.peek16(560),32)==saved['display_list'],'Display list changed')
        antic=b.antic();gtia=b.gtia()
        require(all(antic[key]==saved['antic'][key] for key in ('DMACTL','CHACTL','CHBASE')),'Display hardware changed')
        require(all(gtia[key]==saved['gtia'][key] for key in ('PRIOR','COLPF0','COLPF1','COLPF2','COLPF3','COLBK')),'Color hardware changed')
        require(runtime['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        ownership(b,p,out)
        saved.update(bytes_sha256=hashlib.sha256(saved.pop('bytes')).hexdigest(),editor=saved['editor'].hex(),display_list=saved['display_list'].hex())
        return dict(status='pass',build=p['build'],machine=machine,pin=pin,runtime=runtime,checks=data(b,p['image'],'checks',True),screen_before=saved,observations=observations)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--paced',action='store_true');args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.bank,args.paced)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console display passed',args.case,args.bank,flush=True)
