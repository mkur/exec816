#!/usr/bin/env python3
"""Physical iconification walkthrough of the exact OF816 desktop ZIP."""
import argparse,json,zipfile
from pathlib import Path
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_desktop import layout
from generate_layers import layout as layers_layout
from generate_aes_server import ABI as AES_ABI,expected_layout,layout as aes_layout
from native_program import require,sha256
from test_demo import run


class Iconification:
    def __init__(self,recovery_only=False):
        self.recovery_only=recovery_only

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        types=layout();wf=types['Window']['fields'];sf=types['Service']['fields']
        layers=layers_layout();lf=layers['Layer']['fields']
        results={};s.saved['desktop_menu']={}
        def at(module,name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_'+module+'_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(at('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,old,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                (at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]))
            s.frames(3)
        def button(down):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(int(down)));s.frames(20 if down else 90)
        def click(x,y):
            move(x,y);button(True);button(False)
        menus=Menus(s,click,move)
        def window(title):
            item=next(w for w in menus.windows() if title in w['title'])
            for slot in range(6):
                address=menus.service+sf['windows']+slot*types['Window']['size']
                if s.number(address+wf['id'],4)==item['id']:
                    return dict(**item,address=address,slot=slot)
            raise AssertionError('Missing window')
        def state(w):return s.number(w['address']+wf['iconified'],1)
        def bounds(w,normal=False):
            if normal:address=w['address']+wf['normalBounds']
            else:
                layer=s.number(w['address']+wf['layer'],4)
                scene=menus.service+sf['scene']
                for slot in range(9):
                    address=scene+layers['Scene']['fields']['items']+slot*layers['Layer']['size']
                    if s.number(address,4)==layer:
                        address+=lf['bounds'];break
                else:raise AssertionError('Missing layer')
            return tuple(int.from_bytes(b.memdump(address+i,2),'little',signed=True) for i in (0,2,4,6))
        def view(w):
            shared=json.loads((directory/'c-image.json').read_text())['symbols']
            for index in range(AES_ABI['constants']['CONTEXTS']):
                context=s.number(shared['contexts']+index*4,4)
                if not context:continue
                for slot in range(6):
                    address=s.number(context+dict(expected_layout())['C context views']+slot*4,4)
                    if address:
                        vf=aes_layout()['WindowView']['fields']
                        r=tuple(int.from_bytes(b.memdump(address+vf['bounds']+i,2),'little',signed=True) for i in (0,2,4,6))
                        if r==bounds(w,True):return address,vf
            raise AssertionError('Missing published AES view')
        def hidden(w,original):
            require(state(w)==1,'Iconification did not commit')
            require(bounds(w,True)==original,'Saved normal geometry changed')
            require(bounds(w)==(104+w['slot']*88,222,192+w['slot']*88,238),'Wrong tile bounds')
            require(menus.focus()!=w['id'],'Icon retained keyboard focus')
        def restored(w,original):
            require(state(w)==0 and bounds(w)==original,'Restore lost original bounds')
            require(menus.focus()==w['id'],'Restore did not focus the window')
        def gadget(w):
            l,t,r,bottom=bounds(w)
            kind=s.number(w['address']+wf['frameKind'],2)
            click(r-(24 if kind&4 else 8),t+8)
        def tile(w):click(124+w['slot']*88,230)
        def shot(name):
            move(632,212);s.frames(100);s.cells(name)
            s.save_screen(s.p['output']/(name+'.png'))
        def app(name):
            for _ in range(100):
                found=[a for a in instances(b,s.p,directory) if a['name']==name]
                if found:return found[0]
                s.frames(15)
            raise AssertionError('Missing '+name)

        if self.recovery_only:
            menus.select('SYS:');files=window('SYS:');fb=bounds(files)
            gadget(files);hidden(files,fb)
            menus.select('Shell');shell=window('Shell');sb=bounds(shell)
            gadget(shell);hidden(shell,sb)
            shot('all-windows-iconified')
            focus=menus.focus();menus.key('TAB',ctrl=True)
            require(menus.focus()==focus,'Cycling activated an iconified window')
            menus.select('Shell');restored(shell,sb)
            require(state(files)==1,'Restoring Shell also restored Files')
            menus.select('SYS:');restored(files,fb)
            shot('all-windows-recovered')
            menus.select('Shell');s.command('HELLO',b'Hello from disk!')
            s.save_screen(s.p['output']/'boot-smoke.png')
            self.results=dict(all_windows_iconified=True,cycle_skips_tiles=True,
                              independent_restore=True,windows_menu_recovery=True)
            for char in 'EXIT':s.press(char)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
            return

        menus.select('SYS:');files=window('SYS:');original=bounds(files)
        gadget(files);hidden(files,original)
        address,vf=view(files)
        require(s.number(address+vf['shown'],2)==0 and s.number(address+vf['visibleCount'],2)==0,
                'Iconified AES client retained drawable rectangles')
        shot('files-iconified')
        # Captured release outside and Escape must leave the tile intact.
        move(124+files['slot']*88,230);button(True);move(632,200);button(False)
        hidden(files,original)
        move(124+files['slot']*88,230);button(True);menus.key('ESC');button(False)
        hidden(files,original)
        menus.select('SYS:');restored(files,original);shot('files-menu-restored')
        click(600,8);shot('windows-with-iconify')
        click(472,24+(len(menus.windows())+2)*16)
        hidden(files,original);tile(files);restored(files,original)
        shot('files-tile-restored')
        results.update(aes_geometry=True,empty_visible_region=True,tile_cancel=True,
                       menu_restore=True,tile_restore=True,windows_iconify=True)

        # Real resident Counter timers continue; hidden updates never hit tiles.
        menus.select('Shell');old=s.begin('RUN C:COUNTER.APP');s.ready(old);s.result()
        counter=app('counter')['symbols']['GEMCounter']
        s.rendezvous('dw($%x)=1'%(counter+12));s.frames(100)
        menus.select('Counter');cw=window('Counter');cb=bounds(cw)
        gadget(cw);hidden(cw,cb);before=s.number(counter+14,4)
        s.frames(180)
        require(s.number(counter+14,4)>before,'Iconified Counter stopped')
        shot('counter-iconified')
        menus.select('Counter');restored(cw,cb);shot('counter-restored')
        menus.close();s.frames(80)
        require(not any(a['name']=='counter' for a in instances(b,s.p,directory)),
                'Restored Counter failed to retire')
        results['counter_background_progress']=True

        # Use the active-window menu for Shell; its Close remains disabled.
        menus.select('Shell');shell=window('Shell');sb=bounds(shell)
        old=s.begin('CAT SYS:LONG.TXT')
        click(80,8);click(40,56);hidden(shell,sb)
        from generate_console import constants
        gen=s.saved['top']+constants()['INSTANCE_GENERATION']
        generation=s.number(gen,4)
        # The session's ordinary ready/result path waits for actual command exit.
        s.ready(old);s.result();s.frames(80)
        require(s.number(gen,4)!=generation,'CAT completed before the hidden-output test')
        shot('shell-output-iconified')
        tile(shell);restored(shell,sb);shot('shell-output-restored')
        require(b'CAT reads this file' in s.cells('shell-current-model'),
                'Restored Shell lost completed output')
        results['shell_background_output']=True
        gadget(shell);hidden(shell,sb);menus.select('Shell');restored(shell,sb)
        results['shell_gadget_and_menu']=True
        # A new app reuses the retired slot without inheriting tile state.
        old=s.begin('RUN C:COUNTER.APP');s.ready(old);s.result();app('counter');s.frames(120)
        menus.select('Counter');require(not state(window('Counter')),'Reused slot inherited icon state')
        menus.close();s.frames(100);menus.select('Shell')
        s.command('HELLO',b'Hello from disk!')
        results['slot_reuse_and_teardown']=True
        s.save_screen(s.p['output']/'boot-smoke.png')
        self.results=results
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--recovery-only',action='store_true')
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    probe=Iconification(args.recovery_only)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(tier='development',qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),iconification=probe.results)
    (out/('iconification-recovery.json' if args.recovery_only else 'iconification-results.json')).write_text(json.dumps(result,indent=2)+'\n')
