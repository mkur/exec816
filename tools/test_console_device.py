#!/usr/bin/env python3
"""Execute console requests through the public Exec device API."""
import argparse,json
import generate_tasks
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from test_dos_stack import execute,ownership
from test_console_coexistence import PIN
from os_boundary import emulator,run_to
from test_cooperative import data

def run(t,out,optimize,paced=False):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if paced else PIN
    bridge=ROOT/'build/shell-paced-bridge' if paced else ROOT/'build/console-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned console emulator')
    out.mkdir(parents=True,exist_ok=True)
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        path=directory/'consoledriver.act'
        text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE CONSOLEIDLEPROBE\n')
        needle='        bits=EXEC.Wait($e0000000)'
        require(text.count(needle)==1,'Missing console idle checkpoint')
        text=text.replace(needle,'        CONSOLEIDLEPROBE.Before(0)\n'+needle)
        path.write_text(text)
        return directory
    generate_tasks.policy_modules=instrument
    try:
        p=build(t,ROOT/'tests/programs/native_console_device.act',out,optimize=optimize,
                tasks=True,task_capacity=8,console_test=True,image_data=[(0xd0000,bytes(62))])
    finally:generate_tasks.policy_modules=original

    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        saved={}
        def hw():return {n:b.memdump(a,s).hex() for n,a,s in [('mask',16,1),('skctl',562,1),('key',520,2),('break',566,2)]}
        def guarded_run(condition,frames=600,seconds=30):
            original=b.regs
            def regs():
                current=original()
                pc=int(current['PC'].lstrip('$'),16)
                if pc in (p['labels']['done'],p['labels']['done']+2):
                    status=b.peek16(0x2000)
                    require(status==0xffff,f'Console stopped before input checkpoint: ${status:04x}')
                return current
            b.regs=regs
            b.bp_set(p['labels']['done'],condition='dw($2000)!=$ffff')
            try:run_to(b,p['labels']['native_nmi'],frame_limit=frames,timeout=seconds,condition=condition)
            finally:b.regs=original
        def before(b):
            saved.update(hw());b._cmd_ok('KEY ALL up')
            at=next(d['address'] for d in p['image']['data'] if '_NATIVECONSOLEDEVICE_INPUTREADY_' in d['name'])
            for stage,key in ((1,'A'),(2,'RETURN'),(3,'BREAK')):
                condition=f'db(${at:x})={stage}'
                if stage==1:
                    done=next(d['address'] for d in p['image']['data'] if '_NATIVECONSOLEDEVICE_WRITERDONE_' in d['name'])
                    condition=f'({condition})&(db(${done:x})=1)'
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                guarded_run(condition,12000,240)
                b._cmd_ok(f'KEY {key} down')
                condition=f'@frame>={b.eval_expr("@frame")+4}'
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                if stage==3:break
                guarded_run(condition)
                b._cmd_ok(f'KEY {key} up')
                condition=f'@frame>={b.eval_expr("@frame")+4}'
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                guarded_run(condition)
            b.bp_clear_all()
        try:runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('Device checks',data(b,p['image'],'checks',True),'phase',data(b,p['image'],'phase'),flush=True)
            print('Native status',b.memdump(0x2000,64).hex(),flush=True);raise
        b._cmd_ok('KEY ALL up')
        require(saved==hw(),'Console hardware not restored')
        ownership(b,p,out)
        return dict(status='pass',build=p['build'],machine=machine,pin=pin,runtime=runtime,
                    checks=data(b,p['image'],'checks',True),hardware=saved)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--output',type=Path,required=True)
    a.add_argument('--paced',action='store_true');args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.paced)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console device passed',args.case,flush=True)
