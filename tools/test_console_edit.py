#!/usr/bin/env python3
"""Resumable public CON editing, exclusive input ownership and DOS progress."""
import adapter_state as adapter
from library_paths import read_source
import argparse,json,shutil,os
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine,read_build
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_display import terminal
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,optimize,bank,trace=False,abi_only=False,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    # Count accepted physical keys, without replacing the public Read path.
    source=read_source(ROOT/'lib/dos/doscooked.act').replace('PUBLIC TYPE Handle=', 'PUBLIC CARD keyCount\nPUBLIC BYTE failEcho\nPUBLIC TYPE Handle=')
    source=source.replace('action=COOKEDLINE.Feed(state,state.key)','action=COOKEDLINE.Feed(state,state.key) keyCount==+1')
    source=source.replace('  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope,client)',
        '  IF reading=0 AND failEcho<>0 THEN failEcho=0 request.io_Offset=1 FI\n  error=DOSCANCEL.Transfer(EXEC.IORequest POINTER(request),scope,client)')
    (out/'doscooked.act').write_text(source)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    memory=out/'memory-profile.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/console_edit.act',out,
            optimize=optimize,tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            memory_profile=memory,
            dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)])
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);digest=sha256(media)
    bridge=ROOT/'build/shell-paced-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    def at(name,module='CONSOLEEDITTEST'):
        return next(x['address'] for x in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in x['name'])
    schedule=[];screens=[];saved={}
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in p['labels'].items() if k.startswith(('sio_','native_'))))
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.config('diskemu','fastest');b.mount(0,str(media))
        cs=p['build']['memory']['console_storage'];instance=cs['INSTANCE']
        def far(addr,n):return bytes(b.eval_expr(f'db(${addr+i:x})') for i in range(n))
        def rendezvous(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(adapter.STATE)==0xffff,'CON stopped before checkpoint')
                return r
            b.regs=regs
            try:run_to(b,p['labels']['native_nmi'],12000,240,condition)
            finally:b.regs=original
        def frames(n):rendezvous(f'@frame>={b.eval_expr("@frame")+n}')
        def key(name,state):
            require(b._cmd_ok(f'KEY {name} {state}')['raw_scan'],'Physical key input required')
            schedule.append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
        def press(char):
            count=b.peek16(at('keyCount','DOSCOOKED'))
            ctrl=char in ('\x02','\x03','\x04','→','↑','↓')
            name={'\n':'RETURN','\b':'BACKSPACE','\t':'TAB','\x02':'B','\x03':'C','\x04':'D','!':'BREAK','→':'ASTERISK','↑':'MINUS','↓':'EQUALS'}.get(char,char.upper())
            if ctrl:key('CTRL','down')
            key(name,'down');rendezvous(f'dw(${at("keyCount","DOSCOOKED"):x})={count+1}')
            key(name,'up')
            if ctrl:key('CTRL','up')
            frames(2)
        def phase(number):
            rendezvous(f'db(${at("phase"):x})={number}')
            print('CON checkpoint',number,'checks',b.peek16(at('checks')),flush=True)
        def before(b):
            if trace:b.profile_start()
            saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            b._cmd_ok('KEY ALL up')
            b.poke(at('abiOnly'),int(abi_only))
            cases=[(1,'he\t')] if abi_only else [
                (1,'he\t'),(2,'\t'),(3,'\n'),(4,'x\x04'),(5,'\x04'),
                (6,'bad\t'),(7,'\x04\x03suffix\n'),(8,'ok\n'),
                (9,'cancel\t'),(10,'!'),(11,'ok\n'),(12,'end\t'),
                (13,'a\tb\n'),(14,'\t'),(15,'\n'),
                (16,'echo\t'),(17,'\x04discard\n'),(18,'ok\n'),
                (19,'loss\t'),(20,'suffix\n'),(21,'ok\n')]
            for number,text in cases:
                phase(number)
                if number==1:
                    from console_model import read_cells
                    from generate_console import constants
                    layout=constants()
                    row=int.from_bytes(far(instance+layout['INSTANCE_ROW'],2),'little')
                    column=int.from_bytes(far(instance+layout['INSTANCE_COLUMN'],2),'little')
                    saved['prefix']=read_cells(far,instance)[row*40:row*40+column]
                if number==3:
                    from console_model import read_cells
                    from generate_console import constants
                    layout=constants()
                    cells=read_cells(far,instance)
                    row=int.from_bytes(far(instance+layout['INSTANCE_ROW'],2),'little')
                    wanted=saved['prefix']+b' heLP '
                    require(cells[row*40:(row+1)*40]==wanted.ljust(40,b' '), 'Replacement redraw lost prompt or suffix')
                    require(int.from_bytes(far(instance+layout['INSTANCE_COLUMN'],2),'little')==len(wanted),'Replacement caret differs')
                    screens.append(dict(stage=number,cells=cells.hex()))
                if number==10:
                    key('BREAK','down');frames(3);key('BREAK','up');frames(2)
                    b.poke(at('gate'),1)
                else:
                    b.poke(at('gate'),1)
                    rendezvous(f'(db(${instance+51:x})=2)&(db(${instance+32:x})=0)')
                    for char in text:press(char)
            b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=1200,frame_limit=60000)
        except Exception:
            if trace:b.profile_stop()
            hardware=far(p['build']['task_storage']['BASE']+0x800,128)
            (out/'failure-hardware.bin').write_bytes(hardware)
            print('CON edit failure',data(b,p['image'],'checks',True),data(b,p['image'],'peerChecks',True),far(at('phase'),1).hex(),hex(b.peek16(adapter.STATE)),far(at('event'),4).hex(),far(at('cause'),4).hex(),flush=True);raise
        if trace:b.profile_stop()
        require(data(b,p['image'],'finished')==[1],'CON edit completion missing')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'Console not restored')
        ownership(b,p,out);require(sha256(media)==digest,'Media changed')
        return dict(status='pass',tier='development',abi_only=abi_only,mode='opt' if optimize else 'raw',build=p['build'],runtime=runtime,machine=machine,
                    checks=data(b,p['image'],'checks',True),peer_checks=data(b,p['image'],'peerChecks',True),
                    schedule=schedule,screens=screens,media_sha256=digest,
                    observer_source_sha256=sha256(out/'doscooked.act'),bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--bank',type=int,choices=(2,3),default=2);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--trace',action='store_true')
    a.add_argument('--abi-only',action='store_true')
    a.add_argument('--reuse',action='store_true')
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    try:result=run(out,args.case=='opt',args.bank,args.trace,args.abi_only,args.reuse)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DOS CON edit passed',args.case,args.bank,flush=True)
