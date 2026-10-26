#!/usr/bin/env python3
"""Run the pinned EDX editor through native console I/O and physical keys."""
import argparse
from sdx_test_firmware import select as select_firmware, configure as configure_firmware
import json
from pathlib import Path

import adapter_state as adapter
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN
from generate_console import constants


def fixture(out):
    raw=(ROOT/'build/sdx-inputs/edx/EDX.COM').read_bytes()
    source=out/'probe.act'
    setup=f'  Put(BYTE POINTER(c"RAM:EDX.COM"),BYTE POINTER(ADDRESS($300000)),{len(raw)})\n'
    initial=b'HELLO\x9bSECOND LINE\x9b'
    setup+=f'  Put(BYTE POINTER(c"RAM:EDIT.TXT"),BYTE POINTER(ADDRESS($302000)),{len(initial)})'
    source.write_text((ROOT/'tests/programs/sdx_edx.act').read_text().replace('SETUP_FILES',setup))
    # Observe the production read boundary; do not replace the keyboard or I/O.
    screen=(ROOT/'lib/dos/sdxscreen.act').read_text()
    boundary='; Build an unpublished binding'
    require(screen.count(boundary)==1,'Changed RAWCON module declarations')
    screen=screen.replace(boundary,'PUBLIC CARD keyCalls\nPUBLIC BYTE ARRAY returnedKeys(64),returnedModifiers(64)\n\n'+boundary,1)
    needle='  DO\n    got=DOS.ConsoleIO('
    require(screen.count(needle)==1,'Changed EDX key boundary')
    screen=screen.replace(needle,'  keyCalls==+1\n'+needle)
    screen=screen.replace('        frame(SDXABI.FRAME_P)=frame(SDXABI.FRAME_P) & $7d\n', '        returnedKeys(keyCalls-1)=frame(SDXABI.FRAME_A)\n        returnedModifiers(keyCalls-1)=mods\n        frame(SDXABI.FRAME_P)=frame(SDXABI.FRAME_P) & $7d\n')
    (out/'sdxscreen.act').write_text(screen)
    return source,[(0x300000,raw),(0x302000,initial)]


def run(out,bitmap=False,replay=False,rom=None):
    out.mkdir(parents=True,exist_ok=True)
    if replay:
        p=read_build(out/'program' if bitmap else out)
    else:
        source,payload=fixture(out)
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes']=16384
        memory=out/'memory-profile.json';memory.write_text(json.dumps(profile))
        options=dict(sdx=True,image_data=payload,dos_mounts=[dict(alias='RAM',format=3)],memory_profile=memory)
        if bitmap:
            from build_bitmap_console import build_bitmap
            p=build_bitmap(source,out,release_compiler=True,**options)
        else:
            p=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,
                    task_capacity=8,console=True,console_test=True,**options)
    pin=PIN
    bridge=ROOT/'build/shell-paced-bridge'
    if bitmap:
        from test_mouse_observe import PIN as pin,BRIDGE as bridge
    firmware,pin=select_firmware(rom,pin)
    result=dict(status='running',tier='development',bitmap=bitmap,build=p['build'],pin=pin,keys=[])
    with emulator(bridge,firmware,out,pin=pin) as b:
        configure_firmware(b,firmware)
        for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        result['machine']=verify_machine(b,firmware,pin)
        keyCalls=next(d['address'] for d in p['image']['data'] if '_SDXSCREEN_KEYCALLS_' in d['name'])
        instance=p['build']['memory']['console_storage']['INSTANCE']
        ready=instance+constants()['INSTANCE_READREADY']
        def reach(condition):
            b.bp_clear_all();marker=p['labels']['native_nmi']
            b.bp_set(marker,condition=condition)
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                r=original()
                if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                    require(b.peek16(adapter.STATE)==65535,
                            'Stopped before key: '+str(data(b,p['image'],'checks',True))+' status='+str(b.peek16(adapter.STATE)))
                return r
            b.regs=regs
            try:run_to(b,marker,frame_limit=9000,timeout=60,condition=condition)
            finally:b.regs=original
        def before(b):
            b._cmd_ok('KEY ALL up')
            call=1
            for lap in (1,2,3,4):
                keys=[('INVERSE',False),('E','both'),('BREAK',False)] if lap==3 else [('Z',True),('X',False),('S',True),('RETURN',False),('ESC',False)]
                if lap==4:
                    keys=[('X',False),('CAPS',True),('INVERSE',False),('A',False),('INVERSE',False),('CAPS',False),('CAPS',False),('B',False),('CAPS','shift'),('S',True)]+[(k,False) for k in ['N','E','W','PERIOD','T','X','T','RETURN','ESC']]
                for key,ctrl in keys:
                    reach(f'(dw(${keyCalls:x})={call})&(db(${ready:x})=2)')
                    if key=='INVERSE':
                        # The frozen bridge has no INVERSE key alias. Initialize
                        # the guest's OS inverse state at a protected checkpoint;
                        # all remaining keys use actual POKEY matrix transitions.
                        bank=int.from_bytes(bytes(data(b,p['image'],'guestBank')),'little')
                        address=bank+0x2b6
                        value=b.eval_expr(f'db(${address:x})') ^ 128
                        b.bp_clear_all();b.poke(address,value)
                        result['keys'].append(dict(lap=lap,key='INVFLG',value=value,physical=False))
                        continue
                    if bitmap and lap==1 and key=='Z':
                        from console_model import read_cells
                        from gem_render_oracle import Raster
                        from test_gem_interactive import pixels
                        dirty=instance+constants()['INSTANCE_DIRTYROWS']
                        reach(f'db(${dirty:x})=0')
                        reach(f'@frame>={b.eval_expr("@frame")+3}')
                        cells=read_cells(b.memdump,instance)
                        font=b.memdump(0xe000,1024)
                        raster=Raster(None)
                        for at,ch in enumerate(cells):
                            glyph=ch & 127
                            glyph=(glyph+64 if glyph<32 else glyph-32 if glyph<96 else glyph)
                            for y in range(8):
                                bits=font[glyph*8+y] ^ (255 if ch&128 else 0)
                                for x in range(8):
                                    if bits & (128>>x):raster.pixel(at%80*8+x,at//80*8+y,1)
                        folder=out/'editor-screen';folder.mkdir(exist_ok=True)
                        result['pixels_sha256']=pixels(b,folder,raster.packed())
                        result['cells_hex']=cells.hex()
                    if ctrl is True or ctrl=='both':b._cmd_ok('KEY CTRL down')
                    if ctrl in ('shift','both'):b._cmd_ok('KEY SHIFT down')
                    require(b._cmd_ok(f'KEY {key} down')['raw_scan'],'Physical key required')
                    result['keys'].append(dict(lap=lap,key=key,ctrl=ctrl,frame=b.eval_expr('@frame')))
                    # Escape can retire the last editor before another NMI.
                    if lap==4 and key=='ESC':break
                    reach(f'@frame>={b.eval_expr("@frame")+3}')
                    b._cmd_ok(f'KEY {key} up')
                    if ctrl in ('shift','both'):b._cmd_ok('KEY SHIFT up')
                    if ctrl is True or ctrl=='both':b._cmd_ok('KEY CTRL up')
                    reach(f'@frame>={b.eval_expr("@frame")+3}')
                    if key not in ('CAPS','INVERSE'):call+=1
            b.bp_clear_all()
        try:result['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=9000)
        except Exception:
            b.bp_clear_all()
            print('EDX',dict(checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little'),case=data(b,p['image'],'currentCase',True),primary=data(b,p['image'],'primary',True),secondary=data(b,p['image'],'secondary',True),startFree=data(b,p['image'],'startFree',True),finishFree=data(b,p['image'],'finishFree',True),freeAfter=data(b,p['image'],'freeAfter',True),regs=b.regs()),flush=True)
            bank=int.from_bytes(bytes(data(b,p['image'],'guestBank')),'little')
            (out/'failed-guest.bin').write_bytes(b.memdump(bank,65536))
            raise
        b._cmd_ok('KEY ALL up');ownership(b,p,p['output'])
        actual=bytes(data(b,p['image'],'actual'))[:20]
        require(actual==b'HELLOXX\x9bSECOND LINE\x9b',repr(actual))
        keys=bytes(data(b,p['image'],'returnedKeys'));mods=bytes(data(b,p['image'],'returnedModifiers'))
        require((69,192) in zip(keys,mods),'Inverse changed a Control+Shift shortcut')
        created=bytes(data(b,p['image'],'actual'))[64:67]
        require(created==b'X\x81b',repr(created))
        result.update(status='pass',saved_hex=actual.hex(),created_hex=created.hex(),checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little'))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rom',type=Path)
    parser.add_argument('--bitmap',action='store_true')
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.bitmap,args.replay,args.rom)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('EDX passed',result['checks'],flush=True)
