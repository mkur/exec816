#!/usr/bin/env python3
"""Retained continuation cancellation, input progress, hide and stale identities."""
import argparse,json
import adapter_state as adapter
from pathlib import Path
import generate_tasks
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine
from test_mouse_observe import PIN,BRIDGE,ROM
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from gem_render_oracle import Raster,font_bytes
from bitmap_console_oracle import Terminal
from test_gem_interactive import pixels


def run(out,mode,replay=False,cases=None):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'bitmapcontrolprobe.act').write_bytes((ROOT/'tests/programs/bitmapcontrolprobe.act').read_bytes())
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs);path=directory/'consoledriver.act';s=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE BITMAPCONTROLPROBE\n',1)
        needle='            CONSOLEDISPLAY.Advance(view,instance,entry.unit)'
        require(s.count(needle)==1,'Continuation boundary changed')
        s=s.replace(needle,'            IF BITMAPCONTROLPROBE.hold<>1 THEN\n  '+needle+'\n            FI\n'
            '            IF BITMAPCONTROLPROBE.serviceRead<>0 THEN\n'
            '              BITMAPCONTROLPROBE.serviceRead=0\n'
            '              ReadQuantum(service,instance)\n            FI')
        needle='        again=(writing<>0 AND instance.writeCancel<>0) OR view.scrollState<>0'
        require(s.count(needle)==1,'Continuation scheduling changed')
        s=s.replace(needle,needle+'\n        IF BITMAPCONTROLPROBE.hold<>0 AND view.scrollState<>0 THEN\n          again=0\n        FI')
        needle='  FinishRead(instance,request)'
        require(s.count(needle)==1,'Read completion boundary changed')
        s=s.replace(needle,needle+'\n  IF CONSOLEBITMAP.Pending()<>0 THEN\n    BITMAPCONTROLPROBE.ReadPending(instance)\n  FI')
        path.write_text(s)
        source=ROOT/'lib/console/console-bitmap-display.inc'
        text=source.read_text().replace('PUBLIC PROC Poll(BYTE notified)\n','PUBLIC PROC Poll(BYTE notified)\n  LET pendingControl=CONSOLEWINDOWS.Registry()\n  IF notified<>0 THEN\n    BITMAPCONTROLPROBE.heldNotice=1\n  FI\n  notified=BITMAPCONTROLPROBE.heldNotice\n',1);needle='    CONSOLEBITMAP.Poll()'
        require(text.count(needle)==1,'Async completion boundary changed')
        text=text.replace(needle,
            '    IF BITMAPCONTROLPROBE.hold=2 AND\n'
            '        pendingControl.control.state<>CONSOLETYPES.CTL_PENDING THEN\n'
            '      RETURN\n    FI\n\n'+needle+'\n    BITMAPCONTROLPROBE.heldNotice=0')
        needle='  CONSOLECORE.EditQuantum(instance)'
        require(text.count(needle)==1,'Logical edit boundary changed')
        text=text.replace(needle,needle+'\n  BITMAPCONTROLPROBE.Save(instance)')
        needle='      view.scrollState=3'
        require(text.count(needle)==1,'Async launch boundary changed')
        text=text.replace(needle,needle+'\n      BITMAPCONTROLPROBE.Launched(instance)')
        target=directory/'bitmap-control.inc';target.write_text(text)
        path=directory/'consoledisplay.act'
        path.write_text(path.read_text().replace('USE A816MEMORY\n','USE A816MEMORY\nUSE BITMAPCONTROLPROBE\n',1).replace(str(source),str(target)))
        return directory
    generate_tasks.policy_modules=instrument
    try:p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/console_bitmap_control.act',out,mode=='opt')
    finally:generate_tasks.policy_modules=original
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_BITMAPCONTROL_'+name+'_' in d['name'])
    model=Terminal(80,30)
    for row in range(59):model.feed(bytes([65+row%26])*(79 if row==58 else 80))
    model.feed(b'A');raster=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'));model.paint(raster,0,0,True)
    result=dict(status='running',tier='development',mode=mode,build=p['build'],cases=[])
    try:
        for variant in cases or range(13):
            folder=out/f'case-{variant}';folder.mkdir(exist_ok=True)
            with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
                machine=verify_machine(b,ROM,PIN);saved={};observed={}
                def before(b):
                    b.memload(at('VARIANT'),bytes([variant]));saved['at']=b.peek16(88);saved['screen']=b.memdump(saved['at'],960);saved['display']=b.memdump(0x22f,3)
                    marker=p['labels']['native_nmi'];condition=f'dw(${at("CHECKPOINT"):x})=1'
                    b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    original_regs=b.regs
                    def regs():
                        r=original_regs()
                        if int(r['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                            raise RuntimeError('Control fixture stopped before checkpoint: status='+hex(b.peek16(adapter.STATE))+' checks='+str(b.peek16(at('CHECKS'))))
                        return r
                    b.regs=regs
                    try:run_to(b,marker,condition=condition,frame_limit=15000,timeout=90)
                    except Exception:
                        probe={d['name']:b.memdump(d['address'],min(d['size'],4)).hex() for d in p['image']['data'] if '_BITMAPCONTROLPROBE_' in d['name']}
                        print('Control diagnostics',variant,'checks',b.peek16(at('CHECKS')),'state',hex(b.peek16(adapter.STATE)),probe,flush=True)
                        raise
                    finally:b.regs=original_regs
                    b.bp_clear_all()
                    condition=f'@frame>={b.eval_expr("@frame")+2}';b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=30,timeout=5);b.bp_clear_all()
                    if variant not in (10,11):observed['pixels_sha256']=pixels(b,folder,raster.packed())
                    b.memload(at('GATE'),b'\1\0')
                runtime,_=execute(b,p,before_run=before,frame_limit=8000,timeout=90)
                ownership(b,p,p['output'])
                require(b.memdump(saved['at'],960)==saved['screen'] and b.memdump(0x22f,3)==saved['display'],'OS state changed')
                probes={name:next(d['address'] for d in p['image']['data'] if '_BITMAPCONTROLPROBE_'+name.upper()+'_' in d['name']) for name in ('pendingReads','busyReads','ringChecks')}
                observed.update({name:b.memdump(addr,1)[0] for name,addr in probes.items()})
                if variant>=5:
                    require(observed['pendingReads']>0,'No input read while a scroll was pending')
                    require(observed['ringChecks']==1,'Pending READ changed the committed ring')
                result['cases'].append(dict(variant=variant,machine=machine,runtime=runtime,checks=data(b,p['image'],'checks',True),**observed))
        if any(c['variant']>=5 for c in result['cases']):
            require(any(c['busyReads'] for c in result['cases']),'No read completed during real hardware BUSY')
        result['status']='pass'
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap continuation controls passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--case',type=int,action='append',choices=range(13));a=p.parse_args();run(a.output,a.mode,a.replay,a.case)
