#!/usr/bin/env python3
"""Physical GEM panel controls, independent object pixels and clean retirement."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT,read_build,require,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from desktop_mouse import schedule
from gem_render_oracle import PALETTE,PENS
from stack_budget import stack_usage


def run(out,program):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);f=json.loads((p['output'].parent/'c-image.json').read_text());sy=f['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,build=p['build'],cases=[])
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            base=sy['GEMPanel']; counter=sy['GEMCounter']
            def get(addr,n=2):return int.from_bytes(b.memdump(addr,n),'little')
            def panel(offset,n=2):return get(base+offset,n)
            def state(i):return panel(178+i*24+10)
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Desktop stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
            def frames(n=10):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def until(addr,value=1):reach('dw($%x)=%d'%(addr,value))
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(25)
            def click(x,y):move(x,y);edge(1);edge(0);frames(40)
            def key(name,shift=False):
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                frames(45)
            def snapshot(name):
                move(632,232);frames(90)
                raw=b.memdump(base+178,192);tree=[];strings={}
                for i in range(8):
                    fields=struct.unpack_from('<hhhHHHIhhhh',raw,i*24)
                    tree.append(a.Obj(*fields))
                    if fields[3] in (26,28,32):
                        strings[fields[6]]=a.Text(b.memdump(fields[6],64).split(b'\0')[0].decode('ascii'))
                device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
                aes=a.AES(device,tree,strings);aes.gsx_start()
                x,y,w,h=struct.unpack('<hhhh',b.memdump(base+34,8))
                aes.gsx_sclip(a.Rect(x,y,w,h));aes.ob_draw(0,8)
                focus=tree[panel(392)]
                device.dev.fill_rect(x+focus.ob_x+3,y+focus.ob_y+13,x+focus.ob_x+76,y+focus.ob_y+13,1)
                expected=bytes(device.dev.s.mem[:76800])
                folder=out/name;folder.mkdir(exist_ok=True)
                b.screenshot(str(folder/'scene.png'))
                screen=b.rawscreen(str(folder/'scanout.bgra'));actual=(folder/'scanout.bgra').read_bytes()
                rgb=bytes((n&254)+(n>>7) for n in PALETTE);hardware=[None]*16
                for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
                for py in range(y,y+h):
                    for px in range(x,x+w):
                        byte=expected[py*320+px//2];colour=(byte&15) if px&1 else byte>>4
                        atpixel=py*screen.stride+64+px*4
                        require(actual[atpixel:atpixel+3]==hardware[colour],f'{name} pixel {px},{py}')
                report['cases'].append(dict(name=name,actions=panel(10,4),states=[state(i) for i in range(8)],pixels='match donor oracle',sha256=hashlib.sha256(actual).hexdigest()))
                print(name,'pass',flush=True)
            def before(b):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                until(at('DESKTOPTEST','ready'));frames(180)
                require(panel(8)==1 and get(counter+12)==1,'Applications not ready')
                count=get(counter+14,4)
                click(458,56) # top panel; startup order is intentionally independent
                snapshot('initial')
                click(456,104);require(state(2)==1 and panel(10,4)==1,'Toggle commit')
                snapshot('toggle')
                click(550,136);require(state(4)==0 and state(5)==1,'Radio peers')
                snapshot('radio')
                old=panel(10,4);click(550,104);require(panel(10,4)==old and state(3)==8,'Disabled control')
                move(456,104);edge(1);until(base+394,2)
                move(390,220);edge(0);frames(60)
                require(panel(10,4)==old and state(2)==1 and panel(394)==65535,'Outside release')
                key('TAB');require(panel(392)==4,'Tab skips disabled')
                key('SPACE');require(state(4)==1 and state(5)==0,'Keyboard radio')
                key('TAB',True);require(panel(392)==2,'Shift Tab')
                key('RETURN');require(panel(392)==6 and b.memdump(base+370,8).startswith(b'Applied'),'Default key')
                snapshot('keyboard')
                click(552,176);require(state(2)==0 and state(4)==1 and state(5)==0,'Reset')
                move(456,104);edge(1);key('ESC');edge(0);frames(60)
                require(state(2)==0 and panel(394)==65535,'Escape cancellation')
                snapshot('cancel')
                require(get(counter+14,4)>count,'Counter stalled')
                click(200,40);frames(80);click(458,56);snapshot('focus-repair')
                click(618,56);until(base+8,0)
                require(get(sy['GEMDesktopFailure'])==0,'Application failure')
                b.poke16(at('DESKTOPTEST','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output']);report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(get(sy['GEMDesktopFailure'])==0,'Retirement failure')
            report.update(status='pass',reserved_bank_zero_delta=dict(fixed=0,per_public_task=[0]*8,private_idle=0))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.program.resolve())
