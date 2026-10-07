#!/usr/bin/env python3
"""Physical walkthrough of the exact packaged demo, without target-code observers."""
import adapter_state as adapter
from stack_budget import bank_zero_delta
import argparse
from desktop_mouse import schedule, fast_distance
import json
import re
import shutil
import time
from pathlib import Path
from generate_console import constants as console_constants
from console_model import read_cells
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_console_display import glyph
from test_dos_stack import execute, ownership
from test_shell_core import KEYS


def run(out,stock_smoke=False,loading_smoke=False,boot_smoke=False,bootstrap=None,media_path=None,
        expected_cache=None,cache_smoke=False,cache_override=None,system_drive=1,showcase=False,
        retire_manifest=False, aperture_pattern=None, editing=False,disk_failure=None,measurement_commands=None,distribution_root=None,rom_override=None,disk_boot=False,copy_break=False,profile_commands=True,integration=None):
    require(sum((stock_smoke,loading_smoke,boot_smoke,cache_smoke,showcase,editing,bool(disk_failure))) <= 1,'Select one demo smoke scope')
    require(disk_failure in (None,'missing','missing-work','wrong'),'Unknown disk failure')
    require(measurement_commands is None or boot_smoke,'Measurements require the boot-smoke scope')
    require(not copy_break or (boot_smoke and measurement_commands is not None),
            'COPY BREAK requires the focused command scope')
    require(not disk_boot or bootstrap is None,'Disk Boot requires the XEX bootstrap')
    require(not disk_boot or system_drive!=1,'Disk Boot reserves D1; select SYS on D2-D7')
    distribution_root=Path(distribution_root) if distribution_root is not None else None
    manifest=json.loads((out/'demo-manifest.json').read_text())
    require(all(sha256(out/name)==digest for name,digest in manifest['artifacts'].items()),'Changed demo bundle')
    story=manifest['files']['STORY.TXT']
    story_wc=f'{story["lines"]} {story["words"]} {story["bytes"]}'.encode('ascii')
    story_pair_wc=f'{story["lines"]*2} {story["words"]*2} {story["bytes"]*2}'.encode('ascii')
    p=read_build(out);pin=manifest['pin'];observations=[];saved={}
    if expected_cache is None:expected_cache=p['build']['memory']['boot_config']['cache_blocks']
    bitmap=manifest.get('bitmap',False)
    shell_only=manifest.get('shell_only',False)
    require(not shell_only or boot_smoke or disk_failure,'Shell-only demo requires boot smoke or disk-failure scope')
    desktop=manifest.get('desktop',False)
    counters=manifest.get('aes_counters',False)
    input_apps=manifest.get('aes_input',False)
    gem_apps=counters or input_apps
    foreign=json.loads((out/'bitmap-console/c-image.json').read_text()) if gem_apps else None
    width,height=(64,20) if desktop else (80,30) if bitmap else (40,24)
    shell_cells=width*(height if shell_only else height-6)
    screenshots=[];commands=[]
    boot_image=None
    if bootstrap is None and (disk_boot or showcase or editing or ((boot_smoke or disk_failure) and (shell_only or distribution_root is not None))):
        boot_image=distribution_root/'Exec-of816.xex' if distribution_root is not None else out/manifest['boot_image']
        boot=json.loads((out/manifest['boot_manifest']).read_text())
        require(sha256(boot_image)==boot['xex_sha256'] and
                sha256(out/'program.xex')==boot['exec_xex_sha256'],'Changed OF816 demo image')
        require(sha256(out/'demo-manifest.json')==boot['media']['manifest_sha256'],
                'OF816 image does not match the demo bundle')

        def bootstrap(bridge,native):
            from test_of816 import check_loading_paused, check_loading_complete
            bridge.boot(str(boot_image))
            bridge.bp_set(boot['labels']['of_start'])
            run_to(bridge,boot['labels']['of_start'],3000,90)
            check_loading_paused(bridge,boot,native)
            if system_drive!=boot['boot_config']['system_drive']:
                config=boot['boot_config']
                bridge.memload(config['address']+config['abi']['fields']['system_drive'],bytes([system_drive]))
            bridge.bp_clear_all()
            bridge._cmd_ok('KEY ALL up')
            bridge.bp_set(boot['labels']['of_autoboot'])
            run_to(bridge,boot['labels']['of_autoboot'],1000,30)
            bridge.bp_clear_all()
            start=bridge.eval_expr('@frame')
            bridge.bp_set(boot['labels']['of_handoff'])
            run_to(bridge,boot['labels']['of_handoff'],300,15)
            saved['autoboot_frames']=bridge.eval_expr('@frame')-start
            require(249<=saved['autoboot_frames']<=251,'Autoboot did not wait five PAL seconds')
            from test_of816 import check_boot_guards
            check_boot_guards(bridge,boot['layout'])
            settings=check_loading_paused(bridge,boot,native)
            bridge.bp_clear_all()
            bridge.bp_set(native['labels']['loader_start'])
            run_to(bridge,native['labels']['loader_start'],3000,90)
            check_loading_complete(bridge,boot,native,settings)
            bridge.bp_clear_all()
            bridge.bp_set(native['labels']['start'])
            run_to(bridge,native['labels']['start'],3000,90)
            bridge.bp_clear_all()
    console=console_constants()
    media=manifest.get('media',next(name for name in manifest['artifacts'] if name.endswith('.atr')))
    media_path=Path(media_path) if media_path is not None else (distribution_root or out)/media
    require(sha256(media_path)==manifest['artifacts'][media],'Changed companion media')
    if stock_smoke:require(manifest['mounts'][0]['sector_bytes']==128,'STOCK810 requires 128-byte sectors')
    binary=ROOT/('build/mouse-bridge/AltirraBridgeServer' if bitmap else 'build/shell-paced-bridge/AltirraBridgeServer');rom=ROOT/'build/firmware/altirraos-816.rom'
    if distribution_root is not None:
        rom=distribution_root/'altirraos-816.rom'
    if rom_override is not None:
        rom=Path(rom_override).resolve()
        require(len(rom.read_bytes())==pin['rom']['bytes'],'Diagnostic ROM size differs from platform ROM')
    emulator_hash=pin['mouse_input']['tooling']['sha256'] if bitmap else pin['emulator']['sha256']
    require(sha256(binary)==emulator_hash,'Unpinned demo emulator')
    require(rom_override is not None or sha256(rom)==pin['rom']['sha256'],'Unpinned demo ROM')
    def at(name):return next(d['address'] for d in p['image']['data'] if ('_SHELLAPP_' if shell_only else '_DEMO_')+name.upper()+'_' in d['name'])
    with emulator(binary.parent,rom,out,pin=pin) as b:
        for key,value in manifest['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        if disk_boot:b.config('exeloadmode','diskboot')
        if stock_smoke:b.config('diskemu','810')
        if desktop:b._cmd_ok('MOUSE ST')
        saved['pointer']=(320,120)
        mounted=ROOT/'tests/fixtures/mydos/mydos450-128.atr' if disk_failure=='wrong' else None if disk_failure=='missing' else media_path
        mounted_hash=sha256(mounted) if mounted else None
        if mounted:b.mount(system_drive-1,str(mounted))
        work_media=[]
        for item in manifest.get('additional_media', []):
            target=out/(Path(item['name']).stem+'-walkthrough.atr')
            source=(distribution_root or out)/item['name']
            require(sha256(source)==item['sha256'],'Changed extracted writable media')
            shutil.copyfile(source,target)
            if disk_failure!='missing-work':b.mount(item['drive']-1,str(target))
            work_media.append((item,target))
        machine=verify_machine(b,rom,pin)
        def far(address,length):
            return b''.join((b.eval_expr(f'dw(${address+i:x})')&65535).to_bytes(2,'little') for i in range(0,length,2))[:length]
        def number(address,length=4):return int.from_bytes(far(address,length),'little')
        def pointer(address):return number(address,3)
        def symbol(module,name):
            return next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
        def app(index,field):
            if input_apps:
                from gem_input_oracle import address
                return address(foreign['symbols'],index,field)
            return foreign['symbols']['GEMCounters']+196*index+dict(ready=12,count=14,paints=18,work=38)[field]
        def counter_painter(r,title,bounds):
            if input_apps:
                from gem_input_oracle import state,paint
                require(title in (b'Input A',b'Input B'),'Unexpected GEM input application')
                paint(r,state(b,foreign['symbols'],int(title==b'Input B')),None)
                return
            require(title in (b'Counter A',b'Counter B'),'Unexpected external application')
            index=int(title==b'Counter B');left,top,right,bottom=bounds
            count=number(app(index,'count'))
            r.clip=(left+8,top+16,right-9,bottom-9);r.text=2 if index else 4
            r.apply(8,(left+16,top+30),b'GEM counter')
            r.apply(8,(left+16,top+46),('Count: %06d'%count).encode())
            r.clip=(0,0,639,239)
        def prime_state():
            if shell_only:
                return dict(progress=0,count=0)
            from prime_observer import state
            identity=number(at('job'))
            return state(far,p,out,identity) if identity else dict(progress=0,count=0)
        def rendezvous(condition):
            b.bp_clear_all();marker=p['labels']['native_irq' if desktop else 'native_nmi']
            # Qualify bank zero: the bridge's PC fields and breakpoints use
            # the low word, which can also occur in the linked foreign image.
            condition=f'(@xpc=${marker:x})&({condition})'
            b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                state=original()
                if int(state['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(adapter.STATE)==0xffff,'Demo ended before checkpoint')
                return state
            b.regs=regs
            try:run_to(b,marker,30000 if measurement_commands is not None else 12000,
                       1200 if measurement_commands is not None else 240,condition)
            finally:b.regs=original
        def frames(count=3):rendezvous(f'@frame>={b.eval_expr("@frame")+count}')
        capture=p['build']['memory']['console_storage']['CAPTURE']
        def press(character):
            arrows={'→':'ASTERISK','↑':'MINUS','↓':'EQUALS'}
            ctrl=character in '\x01\x02\x04\x05\x06\x0b\x0c\x0e\x10\x15\x17' or character in arrows
            name,shift=(arrows.get(character,chr(ord(character)+64) if ord(character)<32 else character),False) if ctrl else ('BREAK',False) if character=='\x03' else KEYS[character]
            if ctrl:b._cmd_ok('KEY CTRL down')
            if shift:b._cmd_ok('KEY SHIFT down')
            previous=number(capture+10,2)
            require(b._cmd_ok(f'KEY {name} down')['raw_scan'],'Physical keys required')
            if character=='\x03':frames(3)
            else:rendezvous(f'dw(${capture+10:x})>{previous}')
            b._cmd_ok(f'KEY {name} up')
            if shift:b._cmd_ok('KEY SHIFT up')
            if ctrl:b._cmd_ok('KEY CTRL up')
            frames()
        def ready(previous=None):
            condition=f'(db(${saved["top"]+51:x})=2)&(db(${saved["scope"]+54:x})=0)'
            if previous is not None:
                # Group routes never wrap; the captured tag must have advanced.
                condition+=f'&(dw(${saved["scope"]+14:x})>{previous&65535})'
            rendezvous(condition)
        def cells(label):
            windows=p['build']['memory']['console_storage']['WINDOWS']
            rendezvous(f'db(${windows+console["WINDOWS_PRESENTING"]:x})=0')
            instances=[saved['top']]
            views=[saved['topView']]
            unit=number(windows+console['WINDOWS_PANE'])
            if unit:
                row=windows+console['WINDOWS_ITEMS']+console['WINDOW_SIZE']*(unit&3)
                instances.append(pointer(row+console['WINDOW_INSTANCE']))
                views.append(pointer(row+console['WINDOW_VIEW']))
            # Positioned writes settle before independent pixel comparison.
            write=console['INSTANCE_WRITE']
            condition=f'(db(${windows+console["WINDOWS_PRESENTING"]:x})=0)&'+ '&'.join(f'(dw(${i+write:x})=0)&(db(${i+write+2:x})=0)&'
                f'(db(${i+console["INSTANCE_DIRTYROWS"]:x})=0)&(db(${i+console["INSTANCE_OPERATION"]:x})=0)&'
                f'(db(${v+console["PRESENTATION_SCROLLSTATE"]:x})=0)&'
                f'(dw(${v+10:x})=dw(${i+54:x})+dw(${i+10:x}))'
                for i,v in zip(instances,views))
            if desktop:
                # Console generations can settle while a widget repaint is
                # still inside its C call. Snapshot after that transaction.
                paint=next(d['address'] for d in p['image']['data'] if '_DESKPAINT_PAINTTOKEN_' in d['name'])
                condition+=f'&(dw(${paint:x})=0)'
            rendezvous(condition)
            generations=[number(i+console['INSTANCE_GENERATION']) for i in instances]
            saved['settled_clock']=b.eval_expr('@clk')
            text=b''.join(read_cells(far,i) for i in instances)
            cursor=number(saved['top']+54,2)+number(saved['top']+10,2)
            if bitmap:
                from bitmap_console_oracle import Terminal
                from gem_render_oracle import Raster,font_bytes
                from test_gem_interactive import pixels
                r=Raster(font_bytes(out/manifest['font_source']))
                terminal=Terminal(width,height);terminal.cells[:]=text
                terminal.column=cursor%width;terminal.row=cursor//width
                if desktop:
                    from desktop_oracle import compose
                    packed=compose(b,p,r.font,terminal,saved['pointer'],counter_painter if gem_apps else None)
                else:
                    terminal.paint(r,0,0,caret=True)
                folder=out/f'pixels-{len(observations)}';folder.mkdir(exist_ok=True)
                # Let scanout catch up after the last CPU-side fence.
                frames(2)
                if number(windows+console['WINDOWS_PRESENTING'],1) or unit!=number(windows+console['WINDOWS_PANE']) or generations!=[number(i+console['INSTANCE_GENERATION']) for i in instances]:
                    return cells(label)
                if desktop:
                    # Retained command installation precedes its final paint.
                    # Compare actual scanout with full independent recomposition.
                    from gem_render_oracle import PALETTE,PENS
                    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
                    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                    for attempt in range(200):
                        packed=compose(b,p,r.font,terminal,saved['pointer'],counter_painter if gem_apps else None)
                        frame_data=b.rawscreen(str(folder/'scanout.bgra'))
                        raw=(folder/'scanout.bgra').read_bytes()
                        cropped=b''.join(raw[y*frame_data.stride+64:y*frame_data.stride+2624] for y in range(240))
                        actual=b''.join(cropped[i:i+3] for i in range(0,len(cropped),4))
                        want=b''.join(colors[v>>4]+colors[v&15] for v in packed)
                        if actual==want:break
                        frames(1)
                    require(actual==want,'Desktop scene differs: '+label)
                    pixels(b,folder,packed)
                    print('Desktop scene:',label,flush=True)
                else:
                    pixels(b,folder,r.packed())
            else:
                physical=b.memdump(saved['screen'],960);expected=bytearray(map(glyph,text))
                expected[cursor]^=128
                require(physical==expected,'Physical tile mismatch: '+label)
            if shell_only:
                require(len(text)==width*height,'Shell model dimensions differ from the selected console')
                observations.append(dict(stage=label,guest_frame=b.eval_expr('@frame')))
            else:
                if unit:require(b'PRIME SEARCH' in text[shell_cells:],'Missing prime tile')
                observations.append(dict(stage=label,prime_progress=prime_state()['progress'],prime_count=prime_state()['count'],guest_frame=b.eval_expr('@frame')))
            return text
        def desktop_interaction():
            def symbol(module,name):
                return next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
            def move(x,y):
                x,y=schedule(b,p,saved['pointer'],(x,y))
                rendezvous(f'(dw(${symbol("DESKINPUT","cursorX"):x})={x})&(dw(${symbol("DESKINPUT","cursorY"):x})={y})')
                saved['pointer']=(x,y)
            def button(value):
                b._cmd_ok(f'MOUSE AT 2000 0 0 {value}')
                rendezvous(f'dw(${symbol("DESKINPUT","buttons"):x})={value}')
                frames(2)
            # Fast supported physical motion, followed by a slow inward phase
            # at the clipped corner. Use only controller input on the exact ZIP.
            origin=saved['pointer']
            b._cmd_ok('MOUSE AT 70000 272 272 -1')
            for index in range(80):
                b._cmd_ok(f'MOUSE AT {70000+(16+16*index)*114} 16 16 -1')
            frames(30)
            expected=[min(limit,start+fast_distance(p,97)) for start,limit in zip(origin,(639,239))]
            actual=[number(symbol('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            require(actual==expected,'Packaged fast pointer motion differs')
            saved['pointer']=tuple(actual)
            move(639,239)
            b._cmd_ok('MOUSE AT 70000 -16 -16 -1')
            frames(10)
            step=1 if p['build']['desktop_mouse']['profile']=='mild' else 2
            expected=[639-step,239-step]
            actual=[number(symbol('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            require(actual==expected,'Packaged fine edge reversal differs')
            saved['pointer']=tuple(actual)
            saved['mouse_profile_check']=dict(profile=p['build']['desktop_mouse']['profile'],
                fast_steps_per_axis=97,edge_reversal=actual)
            move(320,120)
            from generate_desktop import layout as desktop_layout
            service=pointer(symbol('DESKSTATE','service'))
            types=desktop_layout()
            context=pointer(service+types['Service']['fields']['windows']
                +types['Window']['size']+types['Window']['fields']['widgets'])
            updates=symbol('DESKAPP','updates')
            def action(x,y,label,states):
                previous=number(updates,2)
                move(x,y);button(1);button(0)
                rendezvous(f'dw(${updates:x})>{previous}')
                rendezvous(f'db(${symbol("DESKAPP","refresh"):x})=0')
                require(number(updates,2)==previous+1,'Duplicate packaged widget action')
                require([number(context+24+i*24+10,2) for i in range(8)]==states,
                        'Packaged widget model differs')
                offset=number(context+24+24+12)
                require(far(context+792+offset,len(label)+1)==label+b'\0','Packaged status patch differs')
                cells(label.decode('ascii'))
            action(480,128,b'Toggle on [2]',[0,0,1,8,1,0,0,0])
            action(584,160,b'Large [5]',[0,0,1,8,0,1,0,0])
            action(480,192,b'Applied [6]',[0,0,1,8,0,1,0,0])
            action(584,192,b'Cancelled [7]',[0,0,1,8,0,1,0,0])
            previous=number(updates,2)
            move(584,128);button(1);button(0)
            frames(6)
            require(number(updates,2)==previous,'Disabled packaged control activated')
            press('\n')
            rendezvous(f'dw(${updates:x})>{previous}')
            rendezvous(f'db(${symbol("DESKAPP","refresh"):x})=0')
            offset=number(context+24+24+12)
            require(far(context+792+offset,12)==b'Applied [6]\0','Return missed default action')
            cells('panel-default-key')
            move(500,86);button(1)
            rendezvous(f'db(${symbol("DESKDRAG","phase"):x})=1')
            move(508,94);button(0)
            rendezvous(f'db(${symbol("DESKDRAG","phase"):x})=0')
            rendezvous(f'dw(${symbol("DESKMOVE","moveToken"):x})=0')
            require(number(symbol('DESKMOVE','moveToken'))==0,'Copied move still awaiting adoption')
            from generate_desktop import layout as desktop_layout
            from generate_layers import layout as layers_layout
            service=pointer(symbol('DESKSTATE','service'))
            scene=service+desktop_layout()['Service']['fields']['scene']
            bounds=scene+layers_layout()['Scene']['fields']['items']+layers_layout()['Layer']['size']+4
            require([number(bounds+i*2,2) for i in range(4)]==[440,88,632,232],'Packaged drag did not commit expected geometry')
            cells('independent-app-drag')
            move(100,100);button(1);button(0)
            cells('shell-focus-restored')
            saved['desktop_interaction']=dict(app_updates=number(updates,2),drag_bounds=[440,88,632,232],pointer=saved['pointer'])

        def counter_interaction(closing=False):
            def move(x,y):
                saved['pointer']=schedule(b,p,saved['pointer'],(x,y))
                x,y=saved['pointer']
                rendezvous(f'(dw(${symbol("DESKINPUT","cursorX"):x})={x})&(dw(${symbol("DESKINPUT","cursorY"):x})={y})')
            def button(value):
                b._cmd_ok(f'MOUSE AT 2000 0 0 {value}')
                rendezvous(f'dw(${symbol("DESKINPUT","buttons"):x})={value}')
                frames(4)
            def work(index):return [number(app(index,'work')+i*2,2) for i in range(4)]
            def click(x,y):move(x,y);button(1);button(0);frames(30)
            require(all(number(app(i,'ready'),2)==1 for i in range(2)),'Missing counter instance')
            before=[number(app(i,'count')) for i in range(2)]
            frames(180)
            require(all(number(app(i,'count'))>before[i] for i in range(2)),'Counter timers stopped')
            if closing:
                x,y,w,h=work(1)
                # Click its visible rightmost title after raising it, then close.
                click(x+w-24,y-10);cells('counter-after-disk-exposure')
                click(x+w-2,y-10)
                rendezvous(f'dw(${foreign["symbols"]["GEMCountersDone"]:x})=1')
                frames(80);cells('counter-physical-close')
                old=number(app(0,'count'));frames(100)
                require(number(app(0,'count'))>old,'Peer counter stopped after close')
                saved['counter_coexistence']['after_disk_counts']=before
                saved['counter_coexistence']['physical_close']=True
            else:
                x,y,w,h=work(1)
                # B extends beyond the shell's right edge after this pixel drag.
                move(x+96,y-10);button(1)
                rendezvous(f'db(${symbol("DESKDRAG","phase"):x})=1')
                move(x+287,y+1);button(0)
                rendezvous(f'(dw(${app(1,"work"):x})={x+191})&(dw(${app(1,"work")+2:x})={y+11})')
                cells('counter-pixel-drag')
                ax,ay,_,_=work(0);click(ax+96,ay-10);cells('counter-A-top')
                x,y,w,h=work(1);click(x+96,y-10);cells('counter-B-top')
                # Sustained high-rate controller input exercises the selected acceleration.
                move(320,120)
                b._cmd_ok('MOUSE AT 70000 272 272 -1')
                for index in range(80):b._cmd_ok(f'MOUSE AT {70000+(16+16*index)*114} 16 16 -1')
                frames(30)
                expected=[min(limit,start+fast_distance(p,97)) for start,limit in zip((320,120),(639,239))]
                actual=[number(symbol('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
                require(actual==expected,'Counter-demo accelerated pointer differs')
                saved['pointer']=tuple(actual)
                saved['mouse_profile_check']=dict(profile=p['build']['desktop_mouse']['profile'],fast_steps_per_axis=97,result=actual)
                saved['counter_coexistence']=dict(initial_counts=before,work=[work(0),work(1)])
            # Native keyboard focus is explicit, including after closing the focused app.
            click(100,32);cells('counter-shell-focus')

        def input_interaction(closing=False):
            from gem_input_oracle import state
            def model(i):return state(b,foreign['symbols'],i)
            def move(x,y):
                saved['pointer']=schedule(b,p,saved['pointer'],(x,y))
                x,y=saved['pointer']
                rendezvous(f'(dw(${symbol("DESKINPUT","cursorX"):x})={x})&(dw(${symbol("DESKINPUT","cursorY"):x})={y})')
            def button(value):
                b._cmd_ok(f'MOUSE AT 2000 0 0 {value}')
                rendezvous(f'dw(${symbol("DESKINPUT","buttons"):x})={value}')
                frames(4)
            def click(x,y):move(x,y);button(1);button(0);frames(30)
            require(all(model(i)['ready'] for i in range(2)),'Missing GEM input instance')
            if closing:
                x,y,w,h=model(1)['work']
                click(x+w-24,y-10);cells('input-after-disk-exposure')
                click(x+w-2,y-10)
                rendezvous(f'dw(${foreign["symbols"]["GEMInputsDone"]:x})=1')
                frames(80);cells('input-physical-close')
                require(model(0)['ready'],'Closing B retired A')
                saved['input_coexistence']['physical_close']=True
            else:
                for i in (0,1):
                    x,y,w,h=model(i)['work'];click(x+96,y-10)
                    old=model(i)['activations'];move(x+48,y+60);button(1)
                    rendezvous(f'dw(${app(i,"armed"):x})=1');cells('input-pressed-'+str(i))
                    button(0);rendezvous(f'dw(${app(i,"activations"):x})={old+1}')
                    cells('input-released-'+str(i))
                    press('A' if i==0 else 'B');frames(20)
                    require(model(i)['key']==('Key: 1E41' if i==0 else 'Key: 3042'),'Packaged GEM key translation differs: '+model(i)['key'])
                    cells('input-key-'+str(i))
                require(model(0)['activations']==model(1)['activations']==1,'Application activation isolation failed')
                # Preserve a visible portion when the shell is raised for disk work.
                x,y,w,h=model(1)['work'];move(x+96,y-10);button(1)
                rendezvous(f'db(${symbol("DESKDRAG","phase"):x})=1')
                move(x+231,y-21);button(0)
                rendezvous(f'(dw(${app(1,"work"):x})={x+135})&(dw(${app(1,"work")+2:x})={y-11})')
                cells('input-pixel-drag')
                saved['input_coexistence']=dict(instances=[model(i) for i in range(2)])
            click(100,32);cells('input-shell-focus')

        def begin(command):
            previous=number(saved['scope']+14)
            for character in command+'\n':press(character)
            return previous
        def result(error=0):
            status=int.from_bytes(far(saved['shell']+32,4),'little',signed=True)
            cause=int.from_bytes(far(saved['shell']+36,4),'little',signed=True)
            require((status,cause)==(10 if error else 0,error),f'Demo command result: {status}/{cause}')
        def command(text,expected=None,error=0):
            print('Demo command:',text,flush=True)
            previous=begin(text);ready(previous);result(error)
            screen=cells(text)
            if expected is not None:require(expected in screen[:shell_cells],'Missing command output: '+text)
            commands.append(text)
            if saved.get('measuring'):
                cache=saved['cache_address']
                saved['cache_commands'].append(dict(command=text,prime_progress=prime_state()['progress'],
                    hits=number(cache+16),misses=number(cache+20),evictions=number(cache+24)))
            return screen
        def writable_commands():
            command('MAKEDIR WORK:NOTES')
            command('COPY SYS:STORY.TXT WORK:NOTES/ONE.TXT')
            command('RENAME WORK:NOTES/ONE.TXT WORK:NOTES/TWO.TXT')
            command('CMP SYS:STORY.TXT WORK:NOTES/TWO.TXT')
            command('CAT SYS:STORY.TXT SYS:STORY.TXT | WC',story_pair_wc)
            command('COPY SYS:STORY.TXT WORK:NOTES/THREE.TXT')
            command('LIST WORK:NOTES/*.TXT NAMES',b'TWO.TXT')
            command('LIST NAMES WORK:NOTES/*.TXT',b'TWO.TXT')
            command('LIST WORK:NOTES/*.TXT NAMES | WC',b'2 2 18')
            command('LIST WORK:NOTES/?WO.TXT NAMES | WC',b'1 1 8')
            command('LIST WORK:NOTES/NO*.TXT',error=205)
            command('LIST WORK:N*TES/*.TXT',error=311)
            command('HELLO | TEE WORK:LOG.TXT',b'Hello from disk!')
            command('HELLO | TEE WORK:LOG.TXT APPEND',b'Hello from disk!')
            command('DELETE WORK:NOTES/TWO.TXT WORK:NOTES/THREE.TXT')
            command('DELETE WORK:NOTES')
            saved['write_commands']=True

        def save_screen(path):
            # Transfer the PNG by file; large inline replies time out on VBXE.
            b.screenshot(str(path))
        def screenshot(name,expected):
            # Wait for the displayed frame, then save exactly what the emulator shows.
            frames(3)
            text=cells(name)
            for fragment in expected:
                require(fragment in text[:shell_cells],'Missing screenshot text: '+fragment.decode('ascii'))
            path=out/name
            save_screen(path)
            screenshots.append(dict(name=name,sha256=sha256(path),commands=list(commands),
                                    rows=[text[i:i+width].decode('ascii').rstrip() for i in range(0,width*height,width)]))
        def ledger():
            memory=p['build']['memory'];base=memory['process_storage']['BASE'];dos=memory['dos_storage']['BASE']
            processes=[(number(base+128*i+77,1),pointer(base+128*i+118),pointer(base+128*i+121)) for i in range(8)]
            objects=[]
            tasks=p['build']['task_storage']
            for i in range(8):
                # Unadmitted DOS rows are uninitialized. Only a live Task owns
                # a published context; its removal also checks the DOS ledger.
                state=number(tasks['BASE']+i*tasks['SIZE']+tasks['TCB_STATE'],1)
                context=pointer(dos+16*i) if state!=tasks['STATE_FREE'] else 0
                objects.append(number(context+68,2) if context else 0)
            require(far(saved['scope']+48,8)==bytes(8),'Retained pipeline group at prompt')
            return dict(live=number(p['build']['task_storage']['LIVE'],1),processes=processes,objects=objects)
        def memory():
            screen=command('MEM')[:shell_cells].decode('ascii')
            values=[int(value) for value in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',screen)]
            require(len(values)>=4,'Incomplete MEM output')
            return values[-4:]
        def active(scope):
            return f'(db(${scope+21:x})=3)&(dw(dw(${scope+27:x})+db(${scope+29:x})*65536+22)=82)'
        def cancel(loading=False):
            print('Demo BREAK:', 'loading' if loading else 'active pipeline',flush=True)
            previous=begin('CAT LONG.TXT | WC')
            if loading:rendezvous(active(saved['scope']))
            else:
                scope=saved['scope']
                rendezvous(f'(db(${scope+54:x})=1)&(dw(${scope+48:x})!=0)&(dw(${scope+51:x})!=0)')
                children=[pointer(scope+offset) for offset in (48,51)]
                rendezvous('|'.join(f'({active(child)})' for child in children))
                require(number(p['build']['task_storage']['LIVE'],1)==7,'Pipeline Task peak differs')
                before=prime_state()['progress'];frames(60)
                require(prime_state()['progress']>before,'Prime display did not advance during file I/O')
                require(number(scope+54,1)==1,'Long pipeline finished before physical BREAK')
            press('\x03');ready(previous);result(304);cells('break-loading' if loading else 'break-pipeline')
            require(ledger()==saved['ledger'],'Ownership retained after BREAK')
        def before(bridge):
            if measurement_commands is not None and profile_commands:b.profile_start('basicblock')
            if aperture_pattern is not None:
                require(b.memdump(0x8000,4096)==aperture_pattern,'Boot changed the reserved VBXE aperture')
            if cache_override is not None:
                boot=p['build']['memory']['boot_config']
                b.memload(boot['address']+boot['abi']['fields']['cache_blocks'],cache_override.to_bytes(2,'little'))
            if stock_smoke:
                from banked_test_memory import write as far_write
                from generate_dos_mounts import encode
                mounts=[{**mount,'profile':2} for mount in manifest['mounts']]
                far_write(b,p['build']['task_storage']['BASE']+0x900,encode(mounts),out)
            if retire_manifest:
                marker=p['labels']['startup_complete']
                b.bp_set(marker);run_to(b,marker,3000,90);b.bp_clear_all()
                boot=p['build']['memory']['constants']
                require(b.peek(boot['RETIRED'])==bytes([1]),'OF816 startup did not retire the manifest')
                b.memload(boot['MANIFEST'],bytes([0xd3])*boot['MANIFEST_CAPACITY'])
            saved.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16))
            saved['screenBytes']=b.memdump(saved['screen'],960);b._cmd_ok('KEY ALL up')
            rendezvous(f'(dw(${at("shell"):x})!=0)|(db(${at("shell")+2:x})!=0)')
            if not shell_only:
                rendezvous(f'db(${at("started"):x})=1')
            saved['shell']=pointer(at('shell'))
            windows=p['build']['memory']['console_storage']['WINDOWS']
            row=windows+console['WINDOWS_ITEMS']
            saved['top']=pointer(row+console['WINDOW_INSTANCE'])
            saved['topView']=pointer(row+console['WINDOW_VIEW'])
            rendezvous(f'db(${saved["top"]+51:x})=2')
            if not shell_only and not disk_failure:
                rendezvous(f'dw(${windows+console["WINDOWS_PANE"]:x})!=0')
            dos=p['build']['memory']['dos_storage']['BASE'];saved['scope']=pointer(pointer(dos)+83)
            ready();cells('startup')
            if integration is not None:
                from types import SimpleNamespace
                try:
                    integration.exercise(SimpleNamespace(b=b,p=p,saved=saved,far=far,number=number,
                        at=at,manifest=manifest,console=console,command=command,begin=begin,
                        result=result,ready=ready,rendezvous=rendezvous,frames=frames,press=press,
                        cells=cells,ledger=ledger,save_screen=save_screen))
                except Exception:
                    diagnostic = dict(pc=b.eval_expr('@xpc'),frame=b.eval_expr('@frame'),
                        read_state=number(saved['top']+51,1),scope=saved['scope'],
                        current_scope=pointer(pointer(dos)+83),scope_bytes=far(saved['scope'],56).hex(),
                        shell=far(saved['shell'],40).hex(),live_tasks=number(p['build']['task_storage']['LIVE'],1),
                        cells=read_cells(far,saved['top']).decode('ascii'))
                    (out/'integration-failure.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
                    raise
                return
            if input_apps:input_interaction()
            elif counters:counter_interaction()
            elif desktop:desktop_interaction()
            if disk_failure:
                require(b'Filesystem startup failed; check configured disks' in cells('failed-mount')[:shell_cells],
                        'Missing bounded system-volume failure message')
                if disk_failure=='missing-work':
                    require(b'Required: WORK: on D8:' in cells('required-work')[:shell_cells],
                            'Missing required companion-drive diagnostic')
                command('ECHO offline',b'offline')
                b.mount(system_drive-1,str(media_path))
                if disk_failure=='missing-work':
                    for item,target in work_media:b.mount(item['drive']-1,str(target))
                if disk_failure in ('missing','missing-work'):
                    previous=begin('CD SYS:');ready(previous);result(8)
                    command('ECHO reset required',b'reset required')
                    cells('bus-offline')
                else:
                    command('CD SYS:')
                    command('SYS:C/ASSIGN C: SYS:C')
                    command('HELLO',b'Hello from disk!')
                    cells('mount-recovered')
                save_screen(out/'walkthrough.png')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if showcase:
                command('TASKS',b'process')
                screenshot('boot-tasks.png',[b'Exec816 (',b'exec: 8 task slots',
                    b'SYS: -> D1: ready, read-only',b'SLOT STATE',b'dos.filesystem',b'process'])
                command('MOUNT',b'SDFS' if manifest.get('filesystem')=='sdfs' else b'MyDOS')
                command('CD SYS:')
                command('DIR',b'STORY')
                command('HELLO',b'Hello from disk!')
                command('TYPE README.TXT',b'Errors are explained on the console.')
                memory()
                command('HELLO | WC',b'1 3 17')
                command('CAT STORY.TXT | WC',story_wc)
                screenshot('walkthrough.png',[b'HELLO | WC',b'1 3 17',
                    b'CAT STORY.TXT | WC',story_wc])
                if work_media:
                    command('ECHO saved >WORK:OUT.TXT')
                    command('CAT WORK:OUT.TXT',b'saved')
                    command('CAT SYS:STORY.TXT >WORK:COPY.TXT')
                    command('CMP SYS:STORY.TXT WORK:COPY.TXT')
                    command('HELLO | WC >WORK:PIPE.TXT')
                    command('CAT WORK:PIPE.TXT',b'1 3 17')
                    saved['filesystem_writes']=True
                    screenshot('writable-files.png',[b'WORK:COPY.TXT',b'WORK:PIPE.TXT',b'1 3 17'])
                    writable_commands()
                require(observations[-1]['prime_progress']>observations[0]['prime_progress'],
                        'Prime display did not advance during the walkthrough')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            # Private diagnostic layouts: DosRegistry.runtime, Service.adapter,
            # Adapter.cache and Cache. The application ABI is unchanged.
            registry=p['build']['memory']['dos_storage']['SHARED']
            service=pointer(registry+68)
            adapter=pointer(service)
            cache=adapter+30
            saved['cache_address']=cache
            settings=p['build']['memory']['boot_config']['settings']
            saved['cache']=dict(requested=number(cache+10,2),blocks=number(cache+12,2),
                                captured=number(settings,2))
            require(all(value==expected_cache for value in saved['cache'].values()),
                    'Effective cache capacity differs from boot request: '+str(saved['cache']))
            if cache_smoke:
                saved['startup_memory']=memory()
                saved['cache_commands']=[]
                saved['measuring']=True
                b.profile_start()
                command('HELLO',b'Hello from disk!')
                command('HELLO',b'Hello from disk!')
                command('CAT STORY.TXT',b'system should also know how to stop.')
                command('WC <STORY.TXT',story_wc)
                saved['memory']=memory();saved['ledger']=ledger()
                command('HELLO',b'Hello from disk!')
                command('CAT STORY.TXT',b'system should also know how to stop.')
                command('WC <STORY.TXT',story_wc)
                command('CAT STORY.TXT | WC',story_wc)
                require(memory()==saved['memory'],'Repeated commands retained heap storage')
                require(ledger()==saved['ledger'],'Repeated commands retained ownership')
                b.profile_stop();saved['measuring']=False
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if boot_smoke:
                startup=cells('system-volume')
                require(f'SYS: -> D{system_drive}: ready, read-only'.encode() in startup[:shell_cells],
                        'Wrong system-volume startup mapping')
                for mount in manifest['mounts']:
                    if mount['alias'].upper() != p['build']['system_mount'].upper():
                        access='read-write' if mount.get('access','readonly')=='readwrite' else 'read-only'
                        status=f"{mount['alias']}: -> D{mount['unit']-48}: ready, {access}".encode()
                        require(status in startup[:shell_cells], 'Missing companion-volume startup status')
                if measurement_commands is not None:
                    saved['measurements']=[]
                    for text in measurement_commands:
                        before_cache=dict(hits=number(cache+16),misses=number(cache+20))
                        command(text)
                        after_cache=dict(hits=number(cache+16),misses=number(cache+20))
                        saved['measurements'].append(dict(command=text,cache_before=before_cache,cache_after=after_cache,
                            settled_clock=saved['settled_clock']))
                    if copy_break:
                        previous=begin('COPY SYS:LONG.TXT WORK:BREAK.TXT')
                        # Current private Service layout: packet at 39,
                        # committing at 453. Stop only after a Write mutation
                        # began, then deliver the real Ctrl-C key.
                        packet=f'dw(${service+39:x})+db(${service+41:x})*65536'
                        rendezvous(f'(db(${service+453:x})=1)&(dw({packet}+22)=87)')
                        started=b.eval_expr('@frame')
                        press('\x03')
                        ready(previous)
                        result(304)
                        cells('copy-break')
                        saved['copy_break_frames']=b.eval_expr('@frame')-started
                        commands.append('COPY SYS:LONG.TXT WORK:BREAK.TXT [Ctrl-C]')
                        command('HELLO',b'Hello from disk!')
                    save_screen(out/'boot-smoke.png')
                    for character in 'EXIT':press(character)
                    b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
                if shell_only:
                    tasks=command('TASKS',b'dos.filesystem')
                    require(b'primes' not in tasks.lower(),'Prime task started in shell-only demo')
                    require(ledger()['live']==(6 if gem_apps else 5 if desktop else 4),'Unexpected shell-only idle Task count')
                    if input_apps:
                        require(b'GEM Input A' in tasks and b'GEM Input B' in tasks,'Missing GEM input Tasks')
                    elif counters:
                        require(b'GEM Counter A' in tasks and b'GEM Counter B' in tasks,'Missing GEM counter Tasks')
                    elif desktop:require(b'desktop-app' in tasks,'Missing independent app Task')
                command('ASSIGN',f'C: -> D{system_drive}:C'.encode())
                command('C:HELLO',b'Hello from disk!')
                command('SYS:C/HELLO',b'Hello from disk!')
                command('SYS:HELLO',b'Object not found (205)',error=205)
                if shell_only:
                    presets=command('ALIAS',b'MKDIR -> MAKEDIR')
                    require(b'LS -> LIST' in presets and b'CP -> COPY' in presets,
                            'Missing default command aliases')
                    cleared=command('CLS')
                    require(cleared==b'> '+b' '*(shell_cells-2),
                            'CLS did not clear the shell and return its prompt home')
                    command('LS *.TXT NAMES',b'STORY.TXT')
                    if work_media:
                        command('CD WORK:')
                        command('mkdir SMOKEDIR')
                        command('CD SMOKEDIR')
                        command('DIR')
                        command('CD ..')
                        command('CD',b'WORK:')
                        command('CD SMOKEDIR')
                        command('COPY SYS:STORY.TXT .',error=210)
                        command('cp SYS:STORY.TXT SMOKE.TXT')
                        command('CMP SYS:STORY.TXT SMOKE.TXT')
                        command('DIR',b'SMOKE.TXT')
                        command('ls',b'SMOKE.TXT')
                        command('DELETE SMOKE.TXT')
                        command('CD ..')
                        command('DELETE SMOKEDIR')
                        command('CD SYS:')
                mounted=command('MOUNT',b'SDFS')
                require(mounted[:shell_cells].count(f'D{system_drive}:   SDFS'.encode())==1,
                        'Mount listing duplicated or omitted the physical volume')
                command('CD SYS:WORK')
                command('CD',f'D{system_drive}:WORK'.encode())
                command('HELLO',b'Hello from disk!')
                command('PATH',b'C:')
                command('HEAD SYS:STORY.TXT LINES 3',b'Exec816')
                command('HEAD MISSING',b'Object not found (205)',error=205)
                command('HEAD ?',b'Arguments: FILE,LINES/K/N')
                # Two DOS names use the same cache. A smaller requested cache
                # can evict file sectors while reloading the TYPE command.
                command(f'TYPE D{system_drive}:STORY.TXT',b'system should also know how to stop.')
                first=dict(hits=number(cache+16),misses=number(cache+20),evictions=number(cache+24))
                command('TYPE SYS:STORY.TXT',b'system should also know how to stop.')
                second=dict(hits=number(cache+16),misses=number(cache+20),evictions=number(cache+24))
                require(second['hits']>first['hits'] and
                        (first['misses']==second['misses'] or
                         (expected_cache<512 and second['evictions']>first['evictions'])),
                        f'Physical and SYS reads did not share the cache: {first} -> {second}')
                saved['sys_cache']=dict(physical=first,system=second)
                if desktop:
                    previous=begin('CAT SYS:STORY.TXT | WC')
                    peak=8 if gem_apps else 7
                    rendezvous(f'db(${p["build"]["task_storage"]["LIVE"]:x})={peak}')
                    saved['desktop_peak_tasks']=peak
                    ready(previous);result()
                    require(story_wc in cells('desktop-pipeline'),'Desktop pipeline result differs')
                    # BREAK must still reach a writer whose obscured console
                    # is draining a full scroll repaint between source quanta.
                    baseline=ledger()
                    previous=begin('CAT SYS:LONG.TXT')
                    # Echoing the command can itself dirty multiple rows. Wait
                    # for CAT's foreground handoff and active console write so
                    # BREAK cannot target the shell before the child starts.
                    window=windows+console['WINDOWS_ITEMS']
                    foreground=window+console['WINDOW_SCOPE']
                    route=f'(dw(${foreground:x})+db(${foreground+2:x})*65536)'
                    write=saved['top']+console['INSTANCE_WRITE']
                    dirty=saved['top']+console['INSTANCE_DIRTYROWS']
                    rendezvous(f'({route}!=0)&({route}!={saved["scope"]})&'
                               f'((dw(${write:x})|db(${write+2:x}))!=0)&(db(${dirty:x})>1)')
                    saved['desktop_scroll_break_checkpoint']=dict(
                        parent_scope=saved['scope'],foreground_scope=pointer(foreground),
                        write=pointer(write),dirty_rows=number(dirty,1))
                    started=b.eval_expr('@clk')
                    press('\x03');ready(previous);result(304)
                    cells('desktop-scroll-break')
                    require(ledger()==baseline,'Obscured scroll BREAK retained ownership')
                    saved['desktop_scroll_break_cycles']=(b.eval_expr('@clk')-started)&0xffffffff
                else:
                    command('CAT SYS:STORY.TXT | WC',story_wc)
                command('CD SYS:')
                if shell_only:command('CD ..')
                command('CD',f'D{system_drive}:'.encode())
                command('HELLO',b'Hello from disk!')
                if desktop and work_media:
                    command('ECHO saved >WORK:OUT.TXT')
                    command('CAT WORK:OUT.TXT',b'saved')
                    command('CAT SYS:STORY.TXT >WORK:COPY.TXT')
                    command('CMP SYS:STORY.TXT WORK:COPY.TXT')
                    command('HELLO | WC >WORK:PIPE.TXT')
                    command('CAT WORK:PIPE.TXT',b'1 3 17')
                    saved['filesystem_writes']=True
                if input_apps:input_interaction(closing=True)
                elif counters:counter_interaction(closing=True)
                frames(3);cells('boot-smoke')
                save_screen(out/'boot-smoke.png')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if editing:
                saved['ledger']=ledger()
                def submit_edited(text,expected):
                    print('Demo edited command:',text,flush=True)
                    previous=begin('');ready(previous);result()
                    screen=cells(text)
                    require(expected in screen[:shell_cells],'Missing edited command output: '+text)
                    commands.append(text)
                def edit(text,caret=None):
                    ready();screen=cells('edit-'+text)
                    row=number(saved['top']+12,2);column=number(saved['top']+10,2)
                    want=b'>  '+text.encode()
                    require(screen[row*width:(row+1)*width]==want+b' '*(width-len(want)),
                            'Edited prompt bytes differ: '+text)
                    require(column==3+(len(text) if caret is None else caret),
                            'Edited prompt caret differs: '+text)
                # The pinned bridge omits PLUS; raw $86 decoding is checked in
                # test_dos_cooked. Exercise its common edit path with Ctrl-B.
                # Movement, insertion, Return away from EOF and deletion keys.
                for char in 'ECHO ac\x02b':press(char)
                edit('ECHO abc',7)
                submit_edited('ECHO abc',b'abc')
                for char in 'ECHO wrong\x01\x06\x06\x06\x06\x06\x0bright':press(char)
                edit('ECHO right')
                submit_edited('ECHO right',b'right')
                for char in 'ECHO two words   \x17ok':press(char)
                edit('ECHO two ok')
                submit_edited('ECHO two ok',b'two ok')
                for char in 'discard\x15ECHO clean\x01\x05\x02→':press(char)
                edit('ECHO clean')
                submit_edited('ECHO clean',b'clean')
                # Ctrl and Atari aliases navigate one ring and restore the draft.
                for char in 'ECHO draft\x02\x02↑':press(char)
                edit('ECHO clean')
                press('↓');edit('ECHO draft',8)
                press('\x10');edit('ECHO clean')
                press('\x0e');edit('ECHO draft',8)
                submit_edited('ECHO draft',b'draft')
                command('HELLO | WC',b'1 3 17')
                press('↑');edit('HELLO | WC');submit_edited('HELLO | WC',b'1 3 17')
                # A loaded CAT reads the inherited CON session with history off.
                saved['memory']=memory()
                previous=begin('CAT')
                parent_client=pointer(saved["scope"]+3)
                condition=f'(db(${saved["top"]+51:x})=2)&(db(${parent_client+86:x})=1)'
                rendezvous(condition)
                for char in '↑programdata\n':press(char)
                rendezvous(condition)
                press('\x04')
                rendezvous(f'db(${parent_client+86:x})=0')
                ready(previous);result();commands.append('CAT (history disabled)')
                require(ledger()==saved['ledger'],'Inherited CON left owned resources')
                press('↑');edit('CAT')
                press('↓');edit('')
                # Editing a recalled line does not modify its saved entry.
                press('↑');press('\x15')
                for char in 'ECHO replacement':press(char)
                press('↓');edit('')
                press('↑');edit('CAT')
                press('\x15')
                for char in 'ECHO after-program':press(char)
                submit_edited('ECHO after-program',b'after-program')
                command('ECHO '+('a'*80),b'a'*80)
                command('ECHO '+('a'*35)+'b\bc',b'a'*35+b'c')
                command('ECHO '+('a'*250),b'a'*80)
                previous=number(saved['scope']+14)
                for character in 'ECHO abandon':press(character)
                press('\x03');ready(previous);result();cells('cancel-edited-line')
                command('ECHO recovered',b'recovered')
                require(memory()==saved['memory'],'Editing/history retained heap storage')
                require(ledger()==saved['ledger'],'Editing/history retained owned resources')
                saved['editing_history']=True
                frames(3);cells('editing');save_screen(out/'walkthrough.png')
                b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY D down')
                b.bp_clear_all();return
            if stock_smoke:
                command('HELLO',b'Hello from disk!')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if loading_smoke:
                command('HELLO',b'Hello from disk!')
                command('CAT STORY.TXT | WC',story_wc)
                saved['memory']=memory();saved['ledger']=ledger()
                cancel(loading=True)
                command('HELLO',b'Hello from disk!')
                require(memory()==saved['memory'],'Loader BREAK retained heap storage')
                require(ledger()==saved['ledger'],'Loader BREAK retained ownership')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            command('MOUNT',b'SDFS' if manifest.get('filesystem')=='sdfs' else b'MyDOS')
            command('CD SYS:')
            command('DIR',b'STORY')
            command('HELLO',b'Hello from disk!')
            command('TYPE README.TXT',b'Errors are explained on the console.')
            command('TASKS',b'process')
            command('HELLO | WC',b'1 3 17')
            command('CAT STORY.TXT | WC',story_wc)
            if work_media:
                command('ECHO saved >WORK:OUT.TXT')
                command('CAT WORK:OUT.TXT',b'saved')
                command('CAT SYS:STORY.TXT >WORK:COPY.TXT')
                command('CMP SYS:STORY.TXT WORK:COPY.TXT')
                command('HELLO | WC >WORK:PIPE.TXT')
                command('CAT WORK:PIPE.TXT',b'1 3 17')
                saved['filesystem_writes']=True
                writable_commands()
            saved['memory']=memory();saved['ledger']=ledger()
            require(saved['ledger']['live']==5,'Idle demo Task count differs')
            for _ in range(2):
                command('HELLO|WC',b'1 3 17')
                command('CAT <STORY.TXT | WC',story_wc)
                require(ledger()==saved['ledger'],'Ownership retained after pipeline')
            cancel(loading=True);command('HELLO | WC',b'1 3 17')
            cancel();command('HELLO | WC',b'1 3 17')
            require(memory()==saved['memory'],'Demo heap did not return to warmed baseline')
            require(ledger()==saved['ledger'],'Demo ownership did not return to baseline')
            # Capture the real final machine display for the guide.
            command('CAT STORY.TXT | WC',story_wc);frames(3);cells('showcase')
            save_screen(out/'walkthrough.png')
            for character in 'EXIT':press(character)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
        if bootstrap is not None:bootstrap(b,p)
        reset_required=disk_failure in ('missing','missing-work')
        runtime,_=execute(b,p,preloaded=bootstrap is not None,before_run=before,timeout=240,frame_limit=12000,
                          expected_status=0xff93 if reset_required else 0)
        if measurement_commands is not None and profile_commands:b.profile_stop()
        b._cmd_ok('KEY ALL up')
        require(number(at('exitStatus'))==0,'Demo EXIT failed')
        require(b.memdump(saved['screen'],960)==saved['screenBytes'] and b.peek(752)==saved['cursor'],'Demo OS display restoration failed')
        if reset_required:
            descriptor=p['build']['task_storage']['BASE']+0x800
            require(number(descriptor+45,1)==1 and pointer(descriptor+12)==pointer(descriptor+16)==0,
                    'Offline SIO retained a caller buffer or lost its reset latch')
        else:
            require(b.peek(16)==saved['mask'],'Demo OS input restoration failed')
            ownership(b,p,out)
        if aperture_pattern is not None:
            require(b.memdump(0x8000,4096)==aperture_pattern,'Shell changed the reserved VBXE aperture')
        if retire_manifest:
            boot=p['build']['memory']['constants']
            require(b.memdump(boot['MANIFEST'],boot['MANIFEST_CAPACITY'])==bytes([0xd3])*boot['MANIFEST_CAPACITY'],
                    'OF816 shell reused retired manifest data')
        require(sha256(media_path)==manifest['artifacts'][media],'Read-only demo media changed')
        if mounted:require(sha256(mounted)==mounted_hash,'Initially mounted media changed')
        saved['work_media']=[]
        if work_media:
            from filesystem_audit import Audit
            time.sleep(3)
            b.regs()
            for item,target in work_media:
                b._cmd_ok(f'EJECT drive={item["drive"]-1}')
                audit=Audit(target.read_bytes())
                allocation=getattr(audit,item['filesystem'])()
                if copy_break:
                    source_files=Audit(media_path.read_bytes())
                    getattr(source_files,manifest['filesystem'])()
                    prefix=audit.files['BREAK.TXT']
                    require(0<len(prefix)<len(source_files.files['LONG.TXT']) and
                            source_files.files['LONG.TXT'].startswith(prefix),
                            'COPY BREAK did not persist an exact confirmed prefix')
                if shell_only and boot_smoke and measurement_commands is None:
                    require(audit.directories==1 and not any(
                        name.startswith('SMOKEDIR/') for name in audit.files),
                        'Bitmap shell write smoke retained its temporary directory')
                if saved.get('filesystem_writes'):
                    require(audit.files['OUT.TXT']==b'saved\n' and audit.files['PIPE.TXT']==b'1 3 17\n'
                            and audit.files['COPY.TXT']==(ROOT/'examples/demo-disk/STORY.TXT').read_bytes(),
                            'Packaged writable walkthrough contents differ')
                if saved.get('write_commands'):
                    require(audit.files['LOG.TXT']==b'Hello from disk!\n'*2 and
                            not any(name.startswith('NOTES/') for name in audit.files),
                            'Packaged writable commands did not persist expected bytes')
                    require(audit.directories==1,'Packaged writable commands retained a directory')
                saved['work_media'].append(dict(name=target.name,sha256=sha256(target),allocation=allocation))
    return dict(status='pass',tier='development',bundle_manifest_sha256=sha256(out/'demo-manifest.json'),
        xex_sha256=sha256(out/'program.xex'),media_sha256=sha256(media_path),screenshot_sha256=sha256(out/'boot-smoke.png') if boot_smoke else None if stock_smoke or loading_smoke or cache_smoke else sha256(out/'walkthrough.png'),
        runner_sha256=sha256(Path(__file__)),runtime=runtime,machine=machine,observations=observations,
        rom=dict(path=str(rom),sha256=sha256(rom),pinned_sha256=pin['rom']['sha256'],override=rom_override is not None),
        screenshots=screenshots,boot_xex_sha256=sha256(boot_image) if boot_image else None,
        autoboot_frames=saved.get('autoboot_frames'),distribution_root=str(distribution_root) if distribution_root else None,
        disk_boot=disk_boot,integration=saved.get('integration'),
        editing_history=saved.get('editing_history',False),write_commands=saved.get('write_commands',False),
        filesystem_writes=saved.get('filesystem_writes',False),work_media=saved.get('work_media'),
        measurements=saved.get('measurements'),desktop_interaction=saved.get('desktop_interaction'),
        mouse_profile_check=saved.get('mouse_profile_check'),counter_coexistence=saved.get('counter_coexistence'),input_coexistence=saved.get('input_coexistence'),
        copy_break_frames=saved.get('copy_break_frames'),
        desktop_scroll_break_cycles=saved.get('desktop_scroll_break_cycles'),
        desktop_scroll_break_checkpoint=saved.get('desktop_scroll_break_checkpoint'),
        cache=saved.get('cache'),cache_commands=saved.get('cache_commands'),startup_memory=saved.get('startup_memory'),
        baseline_memory=saved.get('memory'),baseline_ownership=saved.get('ledger'),peak_tasks=saved.get('desktop_peak_tasks') if desktop else None if stock_smoke or showcase or editing or disk_failure else 6 if shell_only else 7,
        disk_failure=disk_failure,initial_media_sha256=mounted_hash,reset_required=reset_required,
        system_drive=system_drive,sys_cache=saved.get('sys_cache'),retired_manifest_intact=retire_manifest,
        aperture_intact=aperture_pattern is not None,
        scope='Extracted OF816 AES input demo: two independent key/button/timer apps, exact pixels, physical drag/top/close, native shell/disk, eight-Task pipeline, writable media and EXIT' if input_apps else 'Extracted OF816 AES counter demo: two ticking GEM applications, pixel drag/top/close, accelerated pointer, native shell/disk, eight-Task pipeline, writable media and EXIT' if counters else 'Missing companion disk: bounded startup failure, required-drive diagnostic, usable console, persistent offline bus and reset-required EXIT' if disk_failure=='missing-work' else 'Desktop OF816 autoboot, widget toggle/radio/momentary/cancel/disabled/default, client drag/focus, disk commands, writable WORK media, seven-Task pipeline and EXIT' if desktop else 'Missing disk: bounded failure, usable console, persistent offline bus and reset-required EXIT' if reset_required else 'Wrong disk: offline console, CD SYS: recovery, HELLO and EXIT' if disk_failure else 'Cooked control/Atari cursor editing, prompt-only history, draft restoration, 255-byte line, BREAK and Ctrl-D exit' if editing else 'OF816 autoboot and documented commands, with boot and pipeline screenshots' if showcase else 'Repeated HELLO/CAT/WC, pipeline, cache capacity and stable heap' if cache_smoke else 'Bitmap shell OF816 autoboot, C: lookup, aliases, relative subdirectory writes/listing and invalid paths, CAT/WC, pixel oracle and EXIT' if boot_smoke and shell_only and measurement_commands is None else 'Shell boot, disk HELLO, CAT/WC pipeline and EXIT' if boot_smoke else 'Short emulator STOCK810 smoke; mount profile overridden to 2 at bootstrap' if stock_smoke else ('Disk command loading, physical BREAK during loading, recovery and heap/ownership restoration' if loading_smoke else 'Packaged optimized '+manifest.get('filesystem','mydos').upper()+' walkthrough'),bank_zero_delta=bank_zero_delta(p['build']['memory']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--distribution-root',type=Path,help='Use boot image, ROM and disks extracted from the distribution ZIP')
    parser.add_argument('--rom-override',type=Path,help='Explicit diagnostic firmware override; does not qualify a platform')
    parser.add_argument('--disk-boot',action='store_true',help='Use Altirra Disk Boot for the XEX (requires SYS on D2-D7)')
    parser.add_argument('--system-drive',type=int,choices=range(1,8),default=1,help='SYS companion drive (default D1)')
    smoke=parser.add_mutually_exclusive_group()
    smoke.add_argument('--stock-smoke',action='store_true')
    smoke.add_argument('--boot-smoke',action='store_true',help='Check shell, disk commands and EXIT; shell-only builds use OF816 autoboot')
    smoke.add_argument('--loading-smoke',action='store_true',help='Check command loading and physical BREAK without the full walkthrough')
    smoke.add_argument('--editing',action='store_true',help='OF816 boot, physical editing/history, inherited CON, BREAK and EOF')
    smoke.add_argument('--disk-failure',choices=('missing','missing-work','wrong'),help='Check offline console and matching-disk recovery')
    smoke.add_argument('--screenshots',action='store_true',help='Capture boot/TASKS and the documented walkthrough through OF816 autoboot')
    args=parser.parse_args();out=args.bundle.resolve();record=run(out,args.stock_smoke,args.loading_smoke,boot_smoke=args.boot_smoke,showcase=args.screenshots,editing=args.editing,disk_failure=args.disk_failure,distribution_root=args.distribution_root,rom_override=args.rom_override,disk_boot=args.disk_boot,system_drive=args.system_drive)
    (out/(args.disk_failure+'-disk-results.json' if args.disk_failure else 'editing-results.json' if args.editing else 'screenshots-results.json' if args.screenshots else 'stock810-results.json' if args.stock_smoke else 'loading-results.json' if args.loading_smoke else 'demo-results.json')).write_text(json.dumps(record,indent=2)+'\n')
    print('Packaged demo walkthrough passed')
