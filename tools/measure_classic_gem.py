#!/usr/bin/env python3
"""Matched, frame-granular appearance costs on exact OF816 demo packages.

An optional Git revision supplies historical host pixel oracles only. Guest
code always comes from the specified package. This is not the HY4/PI4 matrix.
"""
import argparse,hashlib,json,os,subprocess,sys,types,zipfile
from pathlib import Path
from native_program import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--oracle-revision')
    parser.add_argument('--samples',type=int,default=30)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    for old in (out/'first-focus').glob('*.png'):old.unlink()
    oracle_hashes={}
    if args.oracle_revision:
        for name in ('test_desktop_presentation','desktop_oracle'):
            filename='tools/'+name+'.py'
            source=subprocess.check_output(['git','show',args.oracle_revision+':'+filename],cwd=ROOT)
            oracle_hashes[filename]=hashlib.sha256(source).hexdigest()
            module=types.ModuleType(name);module.__file__=str(ROOT/filename)
            sys.modules[name]=module;exec(compile(source,filename,'exec'),module.__dict__)
    from native_program import read_build,sha256
    from console_turn_profile import flat_markers,analyze_events
    from bitmap_console_performance import native_markers
    from sio_transaction_trace import BASE_HZ,read_events
    from test_demo import run
    from test_desktop_presentation import frame
    from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
    from desktop_menu_check import Menus
    from desktop_mouse import schedule
    from generate_desktop import layout
    from generate_layers import layout as layers
    from gem_applications import symbols
    from measure_desktop import distribution
    bundle=args.bundle.resolve();p=read_build(bundle)
    foreign=json.loads((bundle/'bitmap-console/c-image.json').read_text())
    from dos_concurrent_trace import call_marker
    spans=native_markers(p,[('DESKPAINT_PAINTSTRIP','paint_strip'),('DESKINPUT_SERVICE','input_service'),('CONSOLEDRIVER_COLLECT','collect')])
    mapped={**p,'labels':{**p['labels'],'collect':spans['collect']['entry']}}
    points={'turn':call_marker(mapped,'M_CONSOLEDRIVER_WORKER_','collect'),
            'selected':p['labels']['context_restore']+4,
            'worker_retire':next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_CONSOLEDRIVER_RETIREWORKER_'))}
    for name in ('native_irq','native_nmi','interrupt_schedule'):points[name]=p['labels'][name]
    definition=dict(spans=spans,points=points,task_dps=[pool['dp'] for pool in p['build']['memory']['task_pools']])
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in set(flat_markers(definition).values()))
    os.environ['EXEC816_MASK_TRACE']='0'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    measurements={}
    class Comparison:
        def exercise(self,s):
            b=s.b
            at=lambda mod,name:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+name.upper()+'_' in d['name'])
            font=font_bytes(bundle/s.manifest['font_source'])
            colors={hw:bytes((v&254)+(v>>7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen,hw in enumerate(PENS)}
            def move(x,y):
                position=[s.number(at('DESKINPUT',n)) for n in ('cursorX','cursorY')]
                position=schedule(b,p,position,(x,y));s.saved['pointer']=position
                s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def click(x,y):
                move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(35)
                b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
            menus=Menus(s,click,move);menus.select('Shell');move(632,232);s.frames(60)
            types_=layout();wf=types_['Window']['fields'];lf=layers();sf=lf['Scene']['fields']
            service=menus.service;scene=service+types_['Service']['fields']['scene']
            def active_title():
                ident=menus.focus()
                for slot in range(4):
                    address=service+types_['Service']['fields']['windows']+slot*types_['Window']['size']
                    if s.number(address+wf['id'],4)==ident:break
                else:raise RuntimeError('Missing focused window')
                layer=s.number(address+wf['layer'],4)
                for slot in range(6):
                    loc=scene+sf['items']+slot*lf['Layer']['size']
                    if s.number(loc,4)==layer:break
                else:raise RuntimeError('Missing focused layer')
                bounds=[int.from_bytes(b.memdump(loc+4+i*2,2),'little',signed=True) for i in range(4)]
                title=b.memdump(address+wf['title'],65).split(b'\0')[0]
                model=Raster(font);frame(model,bounds,title,True,close=s.number(address+wf['kind'],1)!=1)
                l,t,r,_=bounds
                expected=b''.join(colors[model.pixels[y*640+x]] for y in range(t,t+16) for x in range(l,r))
                return (l,t,r,t+16),expected,title.decode('ascii')
            def visible(bounds,want):
                path=out/'scanout.bgra';capture=b.rawscreen(str(path));raw=path.read_bytes();l,t,r,bt=bounds
                if i==0:
                    frames=out/'first-focus';frames.mkdir(exist_ok=True)
                    b.screenshot(str(frames/f'{sample:03}.png'))
                got=b''.join(raw[y*capture.stride+64+x*4:y*capture.stride+67+x*4] for y in range(t,bt) for x in range(l,r))
                return got==want
            b.profile_start();focus=[]
            for i in range(args.samples):
                old=menus.focus();b._cmd_ok('KEY CTRL down')
                start=b.eval_expr('@clk')&0xffffffff;b._cmd_ok('KEY TAB down')
                s.rendezvous('dw($%x)!=%d'%(menus.focus_address,old))
                b._cmd_ok('KEY TAB up');b._cmd_ok('KEY CTRL up')
                bounds,want,title=active_title()
                for sample in range(100):
                    if visible(bounds,want):break
                    s.frames(1)
                else:raise RuntimeError('Focused title did not settle: '+title)
                elapsed=((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000
                focus.append(dict(title=title,ms=elapsed));s.frames(15)
            measurements['focus']=dict(samples=focus,**distribution([v['ms'] for v in focus]))
            print('Focus scanout:',distribution([v['ms'] for v in focus]),flush=True)
            menus.select('GEM Control Panel')
            panel=symbols(b,p,bundle/'bitmap-console','panel',s.number(foreign['symbols']['GEMDesktopChildren'],4))['GEMPanel']
            from loadable_gem_feedback import measure
            measure(s,panel,move,'comparison',count=args.samples)
            measurements['button']=s.saved['loaded_panel_feedback']['comparison']
            b.profile_stop();menus.select('Shell')
            (out/'measurements.json').write_text(json.dumps(measurements,indent=2)+'\n')
            s.save_screen(bundle/'boot-smoke.png')
            s.saved['integration']=dict(profile='appearance-cost',samples=args.samples)
            for char in 'EXIT':s.press(char)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
    record=run(bundle,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=Comparison(),profile_commands=False)
    profile=analyze_events(read_events(bundle/'emulator.log'),definition)
    paint=[v for v in profile['routine_spans'] if v['kind']=='paint_strip']
    measurements['paint_units']=dict(count=len(paint),max_cpu_ms=max(v['charged_cpu_ms'] for v in paint),max_elapsed_ms=max(v['elapsed_ms'] for v in paint))
    report=dict(status='pass',tier='development',qualification=False,package_sha256=sha256(bundle/'exec816-demo.zip'),oracle_revision=args.oracle_revision,oracle_hashes=oracle_hashes,
                measurements=measurements,runtime=record['runtime'],scope=f'Same idle shell, Files, ticking Counter and Control Panel; {args.samples} Ctrl-Tab changes and {args.samples} button presses. Submission to matching title/button scanout; PAL-frame polling. Not an HY4/PI4 gate.')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(measurements,indent=2),flush=True)

if __name__=='__main__':main()
