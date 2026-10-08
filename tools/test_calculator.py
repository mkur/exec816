#!/usr/bin/env python3
"""Loaded calculator: physical arithmetic/input, pixels, concurrent counter and cleanup."""
import argparse,json,struct,sys
from pathlib import Path
from native_program import ROOT,read_build,require,verify_machine,sha256
from build_gem_desktop import build_desktop
from build_calculator import build as calculator
from make_data_disk import make
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from test_cooperative import data
from desktop_mouse import schedule
from gem_applications import symbols
from test_shell_core import KEYS
from stack_budget import bank_zero_delta,stack_usage
import adapter_state as adapter


def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:p=read_build(out/'program')
    else:
        calculator(out/'apps/calc')
        p=build_desktop(out,source=ROOT/'tests/programs/calculator_session.act',
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2)])
        media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        for name in ('calc','counter'):
            (media/'C'/(name.upper()+'.APP')).write_bytes((out/'apps'/name/'program.app').read_bytes())
        (media/'CALC.RSC').write_bytes((out/'apps/calc/CALC.RSC').read_bytes())
        make(out/'system.atr',media,binary_names={'C/CALC.APP','C/COUNTER.APP','CALC.RSC'},
             filesystem='sdfs',sector_bytes=256,sectors=2880)
    report=dict(slice='CAL3',status='running',tier='development',qualification=False,
                bank_zero_delta=bank_zero_delta(p['build']['memory']),cases=[])
    at=lambda name:next(d['address'] for d in p['image']['data']
        if '_CALCULATORTEST_'+name.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(out/'system.atr'))
            def get(address,size=2,signed=False):return int.from_bytes(b.memdump(address,size),'little',signed=signed)
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        report['failure_state']=dict(adapter=b.memdump(adapter.STATE,64).hex(),checks=get(at('checks')),ready=get(at('ready')),counter=get(at('counter'),4),calculator=get(at('calculator'),4),sio=b.memdump(int((p['output']/'sio-storage-action.inc').read_text().split('CONST SIO_STATE=$',1)[1].splitlines()[0],16),128).hex())
                        require(b.peek16(adapter.STATE)==65535,'Calculator guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=240,frame_limit=16000)
                finally:b.regs=original
            def frames(n=8):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                cursor=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(cursor('cursorX'),position[0],cursor('cursorY'),position[1]))
                frames(3)
            def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(15)
            def click(x,y):move(x,y);edge(1);edge(0);frames(20)
            def key(name,shift=False):
                if shift:b._cmd_ok('KEY SHIFT down')
                require(b._cmd_ok('KEY '+name+' down')['raw_scan'],'Expected physical key')
                frames(3);b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                frames(20)
            def before(b):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                reach('dw($%x)=1'%at('ready'))
                sy=symbols(b,p,out,'calc',get(at('calculator'),4));model=sy['Calculator']
                reach('dw($%x)=1'%(model+4));frames(100)
                peer=symbols(b,p,out,'counter',get(at('counter'),4))['GEMCounter']
                peer_count=get(peer+14,4)
                def value():return get(sy['shown'],4,True)
                def obj(index):
                    root=get(sy['tree'],4)
                    row=struct.unpack('<hhhHHHIhhhh',b.memdump(root+index*24,24))
                    x,y=struct.unpack('<hh',b.memdump(root+16,4))
                    return x+row[7],y+row[8],row[9],row[10]
                def button(index):
                    x,y,w,h=obj(index);click(x+w//2,y+h//2)
                def text(sequence):
                    for char in sequence:
                        # The pinned bridge has no physical PLUS key.
                        if char in ('~','+'):button(16 if char=='~' else 18)
                        else:key(*KEYS[char])
                def check(sequence,expected,acc=None,fresh=None,pending=0):
                    text(sequence)
                    print('Calculator',sequence,value(),flush=True)
                    require(value()==expected,'Calculator '+sequence+': '+str(value()))
                    require(get(sy['pending'])==pending,'Pending operator '+sequence)
                    if acc is not None:require(get(sy['acc'],4,True)==acc,'Accumulator '+sequence)
                    if fresh is not None:require(get(sy['fresh'])==fresh,'Fresh entry '+sequence)
                    report['cases'].append(dict(keys=sequence,shown=value(),acc=get(sy['acc'],4,True),
                                               pending=get(sy['pending']),fresh=get(sy['fresh'])))
                def display(label):
                    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
                    from test_desktop_presentation import rectangle
                    move(630,230);frames(60)
                    x,y,w,h=obj(2);r=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
                    rectangle(r,(x-1,y-1,x+w+1,y+h+1),1);rectangle(r,(x,y,x+w,y+h),0)
                    r.apply(8,(x+w-88,y+6),str(value()).rjust(11).encode())
                    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
                    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                    path=out/(label+'.bgra');frame=b.rawscreen(str(path));raw=path.read_bytes()
                    for yy in range(y-1,y+h+1):
                        for xx in range(x-1,x+w+1):
                            i=yy*frame.stride+(xx+16)*4
                            require(raw[i:i+3]==colors[r.pixels[yy*640+xx]],label+' display pixels')
                    report.setdefault('pixels',[]).append(label)
                require(value()==0,'Initial calculator value');display('initial')
                for index in (3,10,9,19):button(index)
                require(value()==42,'Physical 7*6=42 including bottom equals');display('forty-two')
                check('C2+3*4=',20,20,1)
                check('C7/3=',2,2,1)
                check('C7~/3=',-2,-2,1)
                check('C1~2',-12,0,0)
                check('C2147483647',2147483647,0,0)
                check('8',2147483647,0,0)
                check('~',-2147483647,0,0)
                display('negative-limit')
                check('C2147483647+1=',1,2147483647,1)
                check('C2147483647*2=',2,2147483647,1)
                check('C2147483647~-1=',1,-2147483647,1)
                check('C1/0=',0,1,1)
                check('C9+1=',10,10,1)
                check('C0~',0,0,0);display('short-zero')
                key('TAB');focus=get(model+6);key('TAB',True)
                require(get(model+6)!=focus,'Shift-Tab did not move focus')
                key(*KEYS['C']);key(*KEYS['7']);key('SPACE');require(value()==77,'Space activation')
                button(18);key(*KEYS['6']);key('RETURN');require(value()==83,'Return default equals')
                # Cancel a held key by outside release and by Escape.
                x,y,w,h=obj(3);old=value();move(x+w//2,y+h//2);edge(1)
                move(630,230);edge(0);require(value()==old,'Outside release activated a key')
                move(x+w//2,y+h//2);edge(1);key('ESC');edge(0)
                require(value()==old and get(model+8)==65535,'Escape did not cancel armed key')
                origin=[get(model+22+i*2) for i in range(2)]
                move(origin[0]+80,origin[1]-8);edge(1)
                move(origin[0]-112,origin[1]+16);edge(0);frames(100)
                actual=[get(model+22+i*2) for i in range(2)]
                require(actual==[origin[0]-192,origin[1]+24],'Calculator drag: '+str((origin,actual)))
                display('moved')
                # Counter covers the calculator; its exposed title brings the calculator back.
                click(220,40);frames(80)
                click(get(model+22)+get(model+26)-8,get(model+24)-8);frames(100);display('exposed')
                require(get(peer+14,4)>peer_count,'Concurrent counter stopped')
                report['stack_live']=stack_usage(b,p['build']['memory'])
                button(20)
                reach('dw($%x)=2'%at('ready'))
                sy=symbols(b,p,out,'calc',get(at('calculator'),4));model=sy['Calculator']
                reach('dw($%x)=1'%(model+4));frames(100)
                require(value()==0 and get(model+18,4)==0,'Reload retained calculator state')
                # Close the reloaded window while a digit is armed.
                x,y,w,h=obj(3);move(x+w//2,y+h//2);edge(1);key('ESC');edge(0)
                x,y,w,h=[get(model+22+i*2) for i in range(4)]
                click(x+w+2,y-8)
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=30000)
            ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[2],'Calculator lifetimes incomplete')
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                          completed=2,stack_usage=stack_usage(b,p['build']['memory']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.replay)
