#!/usr/bin/env python3
"""Physical walkthrough of the exact packaged demo, without target-code observers."""
import adapter_state as adapter
from stack_budget import bank_zero_delta
import argparse
from desktop_mouse import schedule
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
        retire_manifest=False, aperture_pattern=None, editing=False,disk_failure=None,measurement_commands=None,distribution_root=None):
    require(sum((stock_smoke,loading_smoke,boot_smoke,cache_smoke,showcase,editing,bool(disk_failure))) <= 1,'Select one demo smoke scope')
    require(disk_failure in (None,'missing','wrong'),'Unknown disk failure')
    require(measurement_commands is None or boot_smoke,'Measurements require the boot-smoke scope')
    distribution_root=Path(distribution_root) if distribution_root is not None else None
    manifest=json.loads((out/'demo-manifest.json').read_text())
    require(all(sha256(out/name)==digest for name,digest in manifest['artifacts'].items()),'Changed demo bundle')
    p=read_build(out);pin=manifest['pin'];observations=[];saved={}
    if expected_cache is None:expected_cache=p['build']['memory']['boot_config']['cache_blocks']
    bitmap=manifest.get('bitmap',False)
    shell_only=manifest.get('shell_only',False)
    require(not shell_only or boot_smoke,'Shell-only demo currently supports the boot smoke scope')
    desktop=manifest.get('desktop',False)
    width,height=(64,20) if desktop else (80,30) if bitmap else (40,24)
    shell_cells=width*(height if shell_only else height-6)
    screenshots=[];commands=[]
    boot_image=None
    if showcase or (boot_smoke and (shell_only or distribution_root is not None) and bootstrap is None):
        require(bootstrap is None,'The screenshot walkthrough uses the packaged OF816 autoboot')
        boot_image=distribution_root/'Exec-of816.xex' if distribution_root is not None else out/manifest['boot_image']
        boot=json.loads((out/manifest['boot_manifest']).read_text())
        require(sha256(boot_image)==boot['xex_sha256'] and
                sha256(out/'program.xex')==boot['exec_xex_sha256'],'Changed OF816 demo image')
        require(sha256(out/'demo-manifest.json')==boot['media']['manifest_sha256'],
                'OF816 image does not match the demo bundle')

        def bootstrap(bridge,native):
            bridge.boot(str(boot_image))
            bridge.bp_set(boot['labels']['of_start'])
            run_to(bridge,boot['labels']['of_start'],3000,90)
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
    emulator_hash=pin['mouse_input']['tooling']['sha256'] if bitmap else pin['emulator']['sha256']
    require(sha256(binary)==emulator_hash and sha256(rom)==pin['rom']['sha256'],'Unpinned demo machine')
    def at(name):return next(d['address'] for d in p['image']['data'] if ('_SHELLAPP_' if shell_only else '_DEMO_')+name.upper()+'_' in d['name'])
    with emulator(binary.parent,rom,out,pin=pin) as b:
        for key,value in manifest['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
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
            b.mount(item['drive']-1,str(target))
            work_media.append((item,target))
        machine=verify_machine(b,rom,pin)
        def far(address,length):
            return b''.join((b.eval_expr(f'dw(${address+i:x})')&65535).to_bytes(2,'little') for i in range(0,length,2))[:length]
        def number(address,length=4):return int.from_bytes(far(address,length),'little')
        def pointer(address):return number(address,3)
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
            ctrl=character=='\x04'
            name,shift=('D',False) if ctrl else ('BREAK',False) if character=='\x03' else KEYS[character]
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
            instances=[saved['top'],saved['bottom']];views=[saved['topView'],saved['bottomView']]
            if shell_only:instances=instances[:1];views=views[:1]
            # A console write can span multiple source quanta. A synchronized
            # screen halfway through the prime frame's clear/title write is
            # still an intermediate frame, so wait for both writes to finish.
            write=console['INSTANCE_WRITE']
            condition='&'.join(f'(dw(${i+write:x})=0)&(db(${i+write+2:x})=0)&'
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
                    packed=compose(b,p,r.font,terminal,saved['pointer'])
                else:
                    terminal.paint(r,0,0,caret=True)
                folder=out/f'pixels-{len(observations)}';folder.mkdir(exist_ok=True)
                # Let scanout catch up after the last CPU-side fence.
                frames(2)
                if generations!=[number(i+console['INSTANCE_GENERATION']) for i in instances]:
                    return cells(label)
                if desktop:
                    # Retained command installation precedes its final paint.
                    # Compare actual scanout with full independent recomposition.
                    from gem_render_oracle import PALETTE,PENS
                    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
                    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                    for attempt in range(200):
                        packed=compose(b,p,r.font,terminal,saved['pointer'])
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
                require(b'PRIME SEARCH' in text[shell_cells:],'Missing prime tile')
                observations.append(dict(stage=label,prime_frames=number(at('demoFrames')),prime_count=number(at('demoCount'),2),guest_frame=b.eval_expr('@frame')))
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
                saved['cache_commands'].append(dict(command=text,prime_frames=number(at('demoFrames')),
                    hits=number(cache+16),misses=number(cache+20),evictions=number(cache+24)))
            return screen
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
                before=number(at('demoFrames'));frames(60)
                require(number(at('demoFrames'))>before,'Prime display did not advance during file I/O')
                require(number(scope+54,1)==1,'Long pipeline finished before physical BREAK')
            press('\x03');ready(previous);result(304);cells('break-loading' if loading else 'break-pipeline')
            require(ledger()==saved['ledger'],'Ownership retained after BREAK')
        def before(bridge):
            if measurement_commands is not None:b.profile_start('basicblock')
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
            if shell_only:
                rendezvous(f'(dw(${at("shell"):x})!=0)|(db(${at("shell")+2:x})!=0)')
            else:
                rendezvous(f'(db(${at("started"):x})=1)&(dw(${at("demoFrames"):x})>0)')
            saved['shell']=pointer(at('shell'))
            windows=p['build']['memory']['console_storage']['WINDOWS']
            for name,unitName in [('top','demoShellUnit'),('bottom','demoPrimeUnit')]:
                row=windows+console['WINDOWS_ITEMS']+console['WINDOW_SIZE']*(0 if shell_only else number(at(unitName))&3)
                saved[name]=pointer(row+console['WINDOW_INSTANCE'])
                saved[name+'View']=pointer(row+console['WINDOW_VIEW'])
            if shell_only:
                # ShellOpen publishes its allocation before it creates the DOS
                # scope. Observe the first pending read after boot has finished.
                rendezvous(f'db(${saved["top"]+51:x})=2')
            dos=p['build']['memory']['dos_storage']['BASE'];saved['scope']=pointer(pointer(dos)+83)
            ready();cells('startup')
            if desktop:desktop_interaction()
            if disk_failure:
                require(b'SYS: mount failed; use CD SYS: to retry' in cells('failed-mount')[:shell_cells],
                        'Missing bounded system-volume failure message')
                command('ECHO offline',b'offline')
                b.mount(system_drive-1,str(media_path))
                if disk_failure=='missing':
                    previous=begin('CD SYS:');ready(previous);result(8)
                    command('ECHO reset required',b'reset required')
                    cells('bus-offline')
                else:
                    command('CD SYS:')
                    command('HELLO',b'Hello from disk!')
                    cells('mount-recovered')
                save_screen(out/'walkthrough.png')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if showcase:
                command('TASKS',b'primes')
                screenshot('boot-tasks.png',[b'Exec816 (',b'exec: 8 task slots',
                    b'SYS: -> D1: ready, read-only',b'SLOT STATE',b'dos.filesystem',b'primes'])
                command('MOUNT',b'SDFS' if manifest.get('filesystem')=='sdfs' else b'MyDOS')
                command('CD SYS:')
                command('DIR',b'STORY')
                command('HELLO',b'Hello from disk!')
                command('TYPE README.TXT',b'Errors are explained on the console.')
                memory()
                command('HELLO | WC',b'1 3 17')
                command('CAT STORY.TXT | WC',b'24 133 746')
                screenshot('walkthrough.png',[b'HELLO | WC',b'1 3 17',
                    b'CAT STORY.TXT | WC',b'24 133 746'])
                if work_media:
                    command('ECHO saved >WORK:OUT.TXT')
                    command('CAT WORK:OUT.TXT',b'saved')
                    command('CAT SYS:STORY.TXT >WORK:COPY.TXT')
                    command('CMP SYS:STORY.TXT WORK:COPY.TXT')
                    command('HELLO | WC >WORK:PIPE.TXT')
                    command('CAT WORK:PIPE.TXT',b'1 3 17')
                    saved['filesystem_writes']=True
                    screenshot('writable-files.png',[b'WORK:COPY.TXT',b'WORK:PIPE.TXT',b'1 3 17'])
                require(observations[-1]['prime_frames']>observations[0]['prime_frames'],
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
                command('WC <STORY.TXT',b'24 133 746')
                saved['memory']=memory();saved['ledger']=ledger()
                command('HELLO',b'Hello from disk!')
                command('CAT STORY.TXT',b'system should also know how to stop.')
                command('WC <STORY.TXT',b'24 133 746')
                command('CAT STORY.TXT | WC',b'24 133 746')
                require(memory()==saved['memory'],'Repeated commands retained heap storage')
                require(ledger()==saved['ledger'],'Repeated commands retained ownership')
                b.profile_stop();saved['measuring']=False
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if boot_smoke:
                startup=cells('system-volume')
                require(f'SYS: -> D{system_drive}: ready, read-only'.encode() in startup[:shell_cells],
                        'Wrong system-volume startup mapping')
                if measurement_commands is not None:
                    saved['measurements']=[]
                    for text in measurement_commands:
                        before_cache=dict(hits=number(cache+16),misses=number(cache+20))
                        command(text)
                        after_cache=dict(hits=number(cache+16),misses=number(cache+20))
                        saved['measurements'].append(dict(command=text,cache_before=before_cache,cache_after=after_cache,
                            settled_clock=saved['settled_clock']))
                    save_screen(out/'boot-smoke.png')
                    for character in 'EXIT':press(character)
                    b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
                if shell_only:
                    tasks=command('TASKS',b'dos.filesystem')
                    require(b'primes' not in tasks.lower(),'Prime task started in shell-only demo')
                    require(ledger()['live']==(5 if desktop else 4),'Unexpected shell-only idle Task count')
                    if desktop:require(b'desktop-app' in tasks,'Missing independent app Task')
                mounted=command('MOUNT',b'SDFS')
                require(mounted[:shell_cells].count(f'D{system_drive}:   SDFS'.encode())==1,
                        'Mount listing duplicated or omitted the physical volume')
                command('CD SYS:WORK')
                command('CD',f'D{system_drive}:WORK'.encode())
                command('HELLO',b'Hello from disk!')
                command('PATH',b'SYS:')
                command('HEAD SYS:STORY.TXT LINES 3',b'Exec816')
                command('HEAD MISSING',b'Object not found (205)',error=205)
                command('HEAD ?',b'Arguments: FILE,LINES/K/N')
                # Two ordinary DOS names must share the same warmed cache.
                command(f'TYPE D{system_drive}:STORY.TXT',b'system should also know how to stop.')
                first=dict(hits=number(cache+16),misses=number(cache+20))
                command('TYPE SYS:STORY.TXT',b'system should also know how to stop.')
                second=dict(hits=number(cache+16),misses=number(cache+20))
                require(first['misses']==second['misses'] and second['hits']>first['hits'],
                        'Physical and SYS reads did not share the cache')
                saved['sys_cache']=dict(physical=first,system=second)
                if desktop:
                    previous=begin('CAT SYS:STORY.TXT | WC')
                    rendezvous(f'db(${p["build"]["task_storage"]["LIVE"]:x})=7')
                    saved['desktop_peak_tasks']=7
                    ready(previous);result()
                    require(b'24 133 746' in cells('desktop-pipeline'),'Desktop pipeline result differs')
                else:
                    command('CAT SYS:STORY.TXT | WC',b'24 133 746')
                command('CD SYS:')
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
                frames(3);cells('boot-smoke')
                save_screen(out/'boot-smoke.png')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if editing:
                command('ECHO '+('a'*80),b'a'*80)
                # The cooked editor deliberately retains its 36-character tail
                # on either screen width; the command buffer still admits 255.
                command('ECHO '+('a'*35)+'b\bc',b'a'*35+b'c')
                command('ECHO '+('a'*250),b'a'*80)
                previous=number(saved['scope']+14)
                for character in 'ECHO abandon':press(character)
                press('\x03');ready(previous);result();cells('cancel-edited-line')
                command('ECHO recovered',b'recovered')
                frames(3);cells('editing');save_screen(out/'walkthrough.png')
                b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY D down')
                b.bp_clear_all();return
            if stock_smoke:
                command('HELLO',b'Hello from disk!')
                for character in 'EXIT':press(character)
                b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
            if loading_smoke:
                command('HELLO',b'Hello from disk!')
                command('CAT STORY.TXT | WC',b'24 133 746')
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
            command('TASKS',b'primes')
            command('HELLO | WC',b'1 3 17')
            command('CAT STORY.TXT | WC',b'24 133 746')
            if work_media:
                command('ECHO saved >WORK:OUT.TXT')
                command('CAT WORK:OUT.TXT',b'saved')
                command('CAT SYS:STORY.TXT >WORK:COPY.TXT')
                command('CMP SYS:STORY.TXT WORK:COPY.TXT')
                command('HELLO | WC >WORK:PIPE.TXT')
                command('CAT WORK:PIPE.TXT',b'1 3 17')
                saved['filesystem_writes']=True
            saved['memory']=memory();saved['ledger']=ledger()
            require(saved['ledger']['live']==5,'Idle demo Task count differs')
            for _ in range(2):
                command('HELLO|WC',b'1 3 17')
                command('CAT <STORY.TXT | WC',b'24 133 746')
                require(ledger()==saved['ledger'],'Ownership retained after pipeline')
            cancel(loading=True);command('HELLO | WC',b'1 3 17')
            cancel();command('HELLO | WC',b'1 3 17')
            require(memory()==saved['memory'],'Demo heap did not return to warmed baseline')
            require(ledger()==saved['ledger'],'Demo ownership did not return to baseline')
            # Capture the real final machine display for the guide.
            command('CAT STORY.TXT | WC',b'24 133 746');frames(3);cells('showcase')
            save_screen(out/'walkthrough.png')
            for character in 'EXIT':press(character)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
        if bootstrap is not None:bootstrap(b,p)
        reset_required=disk_failure=='missing'
        runtime,_=execute(b,p,preloaded=bootstrap is not None,before_run=before,timeout=240,frame_limit=12000,
                          expected_status=0xff93 if reset_required else 0)
        if measurement_commands is not None:b.profile_stop()
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
                if saved.get('filesystem_writes'):
                    require(audit.files['OUT.TXT']==b'saved\n' and audit.files['PIPE.TXT']==b'1 3 17\n'
                            and audit.files['COPY.TXT']==(ROOT/'examples/demo-disk/STORY.TXT').read_bytes(),
                            'Packaged writable walkthrough contents differ')
                saved['work_media'].append(dict(name=target.name,sha256=sha256(target),allocation=allocation))
    return dict(status='pass',tier='development',bundle_manifest_sha256=sha256(out/'demo-manifest.json'),
        xex_sha256=sha256(out/'program.xex'),media_sha256=sha256(media_path),screenshot_sha256=sha256(out/'boot-smoke.png') if boot_smoke else None if stock_smoke or loading_smoke or cache_smoke else sha256(out/'walkthrough.png'),
        runner_sha256=sha256(Path(__file__)),runtime=runtime,machine=machine,observations=observations,
        screenshots=screenshots,boot_xex_sha256=sha256(boot_image) if boot_image else None,
        autoboot_frames=saved.get('autoboot_frames'),distribution_root=str(distribution_root) if distribution_root else None,
        filesystem_writes=saved.get('filesystem_writes',False),work_media=saved.get('work_media'),
        measurements=saved.get('measurements'),desktop_interaction=saved.get('desktop_interaction'),
        cache=saved.get('cache'),cache_commands=saved.get('cache_commands'),startup_memory=saved.get('startup_memory'),
        baseline_memory=saved.get('memory'),baseline_ownership=saved.get('ledger'),peak_tasks=saved.get('desktop_peak_tasks') if desktop else None if stock_smoke or showcase or editing or disk_failure else 6 if shell_only else 7,
        disk_failure=disk_failure,initial_media_sha256=mounted_hash,reset_required=reset_required,
        system_drive=system_drive,sys_cache=saved.get('sys_cache'),retired_manifest_intact=retire_manifest,
        aperture_intact=aperture_pattern is not None,
        scope='Desktop OF816 autoboot, widget toggle/radio/momentary/cancel/disabled/default, client drag/focus, disk commands, writable WORK media, seven-Task pipeline and EXIT' if desktop else 'Missing disk: bounded failure, usable console, persistent offline bus and reset-required EXIT' if reset_required else 'Wrong disk: offline console, CD SYS: recovery, HELLO and EXIT' if disk_failure else 'Cooked 36/37-column edits, 255-byte command, BREAK recovery and physical Ctrl-D exit' if editing else 'OF816 autoboot and documented commands, with boot and pipeline screenshots' if showcase else 'Repeated HELLO/CAT/WC, pipeline, cache capacity and stable heap' if cache_smoke else 'Shell boot, disk HELLO, CAT/WC pipeline and EXIT' if boot_smoke else 'Short emulator STOCK810 smoke; mount profile overridden to 2 at bootstrap' if stock_smoke else ('Disk command loading, physical BREAK during loading, recovery and heap/ownership restoration' if loading_smoke else 'Packaged optimized '+manifest.get('filesystem','mydos').upper()+' walkthrough'),bank_zero_delta=bank_zero_delta(p['build']['memory']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--distribution-root',type=Path,help='Use boot image, ROM and disks extracted from the distribution ZIP')
    smoke=parser.add_mutually_exclusive_group()
    smoke.add_argument('--stock-smoke',action='store_true')
    smoke.add_argument('--boot-smoke',action='store_true',help='Check shell, disk commands and EXIT; shell-only builds use OF816 autoboot')
    smoke.add_argument('--loading-smoke',action='store_true',help='Check command loading and physical BREAK without the full walkthrough')
    smoke.add_argument('--editing',action='store_true',help='Physical long-line editing, BREAK and EOF')
    smoke.add_argument('--disk-failure',choices=('missing','wrong'),help='Check offline console and matching-disk recovery')
    smoke.add_argument('--screenshots',action='store_true',help='Capture boot/TASKS and the documented walkthrough through OF816 autoboot')
    args=parser.parse_args();out=args.bundle.resolve();record=run(out,args.stock_smoke,args.loading_smoke,boot_smoke=args.boot_smoke,showcase=args.screenshots,editing=args.editing,disk_failure=args.disk_failure,distribution_root=args.distribution_root)
    (out/(args.disk_failure+'-disk-results.json' if args.disk_failure else 'editing-results.json' if args.editing else 'screenshots-results.json' if args.screenshots else 'stock810-results.json' if args.stock_smoke else 'loading-results.json' if args.loading_smoke else 'demo-results.json')).write_text(json.dumps(record,indent=2)+'\n')
    print('Packaged demo walkthrough passed')
