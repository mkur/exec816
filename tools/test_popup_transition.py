#!/usr/bin/env python3
"""Presenter-owned saved popup copies with VRAM and failure-boundary checks."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
import generate_tasks
from build_bitmap_console import build_bitmap
from generate_layers import layout
from native_program import ROOT, read_build, require, verify_machine, sha256
from library_paths import read_source
from os_boundary import emulator, run_to
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from stack_budget import stack_usage
from gem_render_oracle import DESKTOP_PALETTE


def instrument(original):
    def prepare(*args, **kwargs):
        directory = original(*args, **kwargs)
        launcher=directory.parent.parent/'launcher.act'
        source=launcher.read_text().replace('USE EXEC\n','USE EXEC\nUSE AESBOOT\n',1)
        source=source.replace('  IF CONSOLEDRIVER.Start()=0 THEN',
            '  BEGIN\n    LET enabled=AESBOOT.Enable()\n  END\n  IF CONSOLEDRIVER.Start()=0 THEN',1)
        source=source.replace('  IF DESKBOOT.StopAdmission()=0 THEN',
            '  BEGIN\n    LET stopped=AESBOOT.StopAdmission()\n  END\n  IF DESKBOOT.StopAdmission()=0 THEN',1)
        source=source.replace('  DESKBOOT.Disable()\n\nRETURN',
            '  AESBOOT.Disable()\n  DESKBOOT.Disable()\n\nRETURN')
        launcher.write_text(source)
        (directory/'popupprobe.act').write_text((ROOT/'tests/programs/popupprobe.act').read_text())
        (directory/'popupfault.act').write_text('MODULE POPUPFAULT\nPUBLIC BYTE failed,blocked,failStart,active\nENDMODULE\n')
        for name in ('deskhost', 'deskmenu', 'deskpaint', 'consoledisplay'):
            path=directory/(name+'.act');s=(path.read_text() if name=='consoledisplay' else read_source(ROOT/'lib/desktop'/(name+'.act'))).replace('USE EXEC\n','USE EXEC\nUSE POPUPPROBE\n',1)
            if 'USE POPUPPROBE' not in s:s=s.replace('MODULE '+name.upper()+'\n','MODULE '+name.upper()+'\nUSE POPUPPROBE\n')
            if name=='deskhost':
                at=s.index('PUBLIC BYTE FUNC Cache()');pos=s.index('  LET service=',at)
                s=s[:pos]+'  IF POPUPPROBE.active<>0 THEN RETURN(0) FI\n'+s[pos:]
                s=s.replace('PUBLIC PROC MenuContinuation()\n','PUBLIC PROC MenuContinuation()\n\n  IF POPUPPROBE.active<>0 THEN RETURN FI\n')
                s=s.replace('  LET service=DESKSTATE.Get()\n  IF service<>NULL AND service.live<>0 THEN\n    priorToken=',
                    '  POPUPPROBE.Pump()\n  IF POPUPPROBE.active<>0 THEN RETURN FI\n  LET service=DESKSTATE.Get()\n  IF service<>NULL AND service.live<>0 THEN\n    priorToken=')
            elif name=='deskmenu':
                at=s.index('PUBLIC PROC Advance()');pos=s.index('  LET service=',at)
                s=s[:pos]+'  IF POPUPPROBE.active<>0 THEN RETURN FI\n'+s[pos:]
            elif name=='consoledisplay':
                s=s.replace('USE POPUPPROBE','USE POPUPFAULT')
                at=s.index('PUBLIC PROC Present(');pos=s.index('  LET ',at)
                s=s[:pos]+'  IF POPUPFAULT.active<>0 THEN RETURN FI\n'+s[pos:]
            else:
                at=s.index('PUBLIC PROC Sync()');pos=s.index('  LET service=',at)
                s=s[:pos]+'  IF POPUPPROBE.active<>0 THEN RETURN FI\n'+s[pos:]
                at=s.index('PUBLIC BYTE FUNC Pump(');p=s.index('  LET service=',at)
                s=s[:p]+'  IF POPUPPROBE.active<>0 THEN RETURN(0) FI\n'+s[p:]
            path.write_text(s)
        path=directory/'deskmenucache.act';s=read_source(ROOT/'lib/desktop/deskmenucache.act').replace('USE DISPLAY\n','USE DISPLAY\nUSE POPUPFAULT\n')
        s=s.replace('CONSOLEBITMAP.Failed()<>0','(CONSOLEBITMAP.Failed()<>0 OR POPUPFAULT.failed<>0)')
        s=s.replace('DISPLAY.Blocked()<>0','(DISPLAY.Blocked()<>0 OR POPUPFAULT.blocked<>0)')
        # Start rejection occurs before touching the device. Other failures are
        # observed after real DMA, so repair must assume changed destination pixels.
        s=s.replace('RETURN(CONSOLEBITMAP.CopyStart())',
            '  IF POPUPFAULT.failStart<>0 THEN\n    POPUPFAULT.failStart=0\n    RETURN(0)\n  FI\n\nRETURN(CONSOLEBITMAP.CopyStart())')
        path.write_text(s)
        return directory
    return prepare


def run(out, replay=False):
    out.mkdir(parents=True,exist_ok=True)
    original=generate_tasks.policy_modules
    generate_tasks.policy_modules=instrument(original)
    try:
        p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/popup_transition.act',out,
            desktop=True,release_compiler=True)
    finally:generate_tasks.policy_modules=original
    report=dict(tier='development',qualification=False,status='running',cases=[],build=p['build'],
        inputs={name:sha256(ROOT/name) for name in ('lib/desktop/deskmenucache.act',
            'tools/test_popup_transition.py','tests/programs/popupprobe.act','tests/programs/popup_transition.act')})
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def before(_):
                get=lambda a,n=1:int.from_bytes(b.memdump(a,n),'little')
                def reach(condition):
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    b.bp_set(adapter.RESIDENT_EXIT)
                    try:
                        run_to(b,p['labels']['native_irq'],condition=condition,timeout=20,frame_limit=1000)
                    except Exception:
                        print('Stopped',condition,b.regs(), 'adapter',b.peek16(adapter.STATE),flush=True)
                        for module,names in [('POPUPPROBE',['command','ready','active','checks']),('DESKMENUCACHE',['token']),('DESKSTATE',['service'])]:
                            print(module,{n:get(at(module,n),4) for n in names},flush=True)
                        from generate_desktop import layout as dl
                        sc=get(at('DESKSTATE','service'),3)+dl()['Service']['fields']['scene']
                        print('Scene',{n:get(sc+o,4) for n,o in layout()['Scene']['fields'].items() if n in ('busy','visibleDamage','rebuilds')},flush=True)
                        raise
                def cmd(value):
                    print('Popup command',value,flush=True)
                    b.memload(at('POPUPPROBE','command'),bytes([value]));reach('db($%x)=0'%at('POPUPPROBE','command'))
                def fault(name,value):b.memload(at('POPUPFAULT',name),bytes([value]))
                def state():
                    from generate_desktop import layout as desk_layout
                    scene=get(at('DESKSTATE','service'),3)+desk_layout()['Service']['fields']['scene']
                    def f(name,size=4):return get(scene+layout()['Scene']['fields'][name],size)
                    under=scene+layout()['Scene']['fields']['under']+layout()['SavedArea']['fields']['slot']
                    slots=scene+layout()['Scene']['fields']['items']
                    stride=layout()['Layer']['size'];fields=layout()['Layer']['fields']
                    popup_id=get(at('DESKSTATE','popupLayer'),4)
                    popup=next(slots+i*stride for i in range(9) if get(slots+i*stride,4)==popup_id)
                    return dict(dirty=get(popup+fields['dirty']),busy=f('busy'),rebuilds=f('rebuilds'),pin=get(under+layout()['CacheSlot']['fields']['pinned']),
                        valid=get(under+layout()['CacheSlot']['fields']['valid']),phase=get(at('DESKSTATE','menuReplacing')))
                def pixels(old=False,new=False):
                    reach('@frame>=%d'%(b.eval_expr('@frame')+2))
                    capture=out/'pixels.bgra';frame=b.rawscreen(str(capture));raw=capture.read_bytes()
                    rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
                    require((frame.width,frame.height)==(672,240),'Wrong scanout')
                    for y in range(24,88):
                        for x in range(48,240):
                            pen=5 if new and 104<=x<216 and 28<=y<76 else 4 if old and 48<=x<128 and 32<=y<64 else 2
                            at=y*frame.stride+64+x*4
                            require(raw[at:at+3]==rgb[pen*3:pen*3+3][::-1],f'Pixel {x},{y} differs')
                reach('db($%x)=1'%at('POPUPPROBE','ready'))
                cmd(1);cmd(2);cmd(3);pixels(old=True)
                prior_token=0
                for name in ('hit','miss','background-start','background-failure','popup-start','popup-failure','stale-save','stale-key'):
                    if name!='hit':
                        cmd(7);cmd(2);cmd(3)
                    if name=='miss':cmd(8)
                    if name=='background-start':fault('failStart',1)
                    base=state();cmd(4);s=state()
                    require(s['busy'] and s['pin']==1 and s['rebuilds']==base['rebuilds'],f'Admission changed scene: {base} -> {s}, result {get(at("POPUPPROBE","result"),2)}')
                    b.memload(at('POPUPPROBE','token'),prior_token.to_bytes(4,'little'));cmd(12)
                    require(state()==s,'Stale completion changed the live transaction')
                    prior_token=s['busy']
                    if name=='background-failure':fault('failed',1)
                    if name=='popup-start':fault('failStart',1)
                    if name=='stale-save':cmd(9)
                    if name=='stale-key':cmd(11)
                    fault('blocked',1);cmd(5);held=state()
                    require(held['busy']==s['busy'] and held['pin']==1,'Unquiesced copy released')
                    fault('blocked',0);cmd(5);s=state()
                    if s['phase']==2:
                        require(s['busy']==held['busy'] and s['rebuilds']==base['rebuilds'],'Second copy released scene')
                        if name=='popup-failure':fault('failed',1)
                        cmd(5);s=state()
                    require(s['phase']==3 and s['busy']==0 and s['pin']==0,'Incomplete retirement')
                    cmd(6);outcome=get(at('POPUPPROBE','result'),2)
                    expected=1 if name=='hit' else 2 if name in ('miss','popup-start','popup-failure') else 3
                    require(outcome==expected,f'{name}: outcome {outcome}')
                    require(s['rebuilds']==base['rebuilds']+(expected!=3),'Unexpected rebuild count')
                    require(s['dirty']==(expected!=1),'Incorrect popup damage after retirement')
                    require(s['valid']==(expected!=3),'Incorrect saved background lifetime')
                    if name=='hit':pixels(new=True)
                    if name in ('miss','popup-start'):pixels()
                    report['cases'].append(dict(name=name,outcome=outcome,state=s))
                    fault('failed',0)
                cmd(10);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output']);report['stack_usage']=stack_usage(b,p['build']['memory'])
            report['checks']=int.from_bytes(b.memdump(at('POPUPPROBE','checks'),2),'little')
        report['status']='pass'
    except Exception as e:
        report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Popup transition passed',len(report['cases']),'cases')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--replay',action='store_true')
    args=ap.parse_args();run(args.output.resolve(),args.replay)
