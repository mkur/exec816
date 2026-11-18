#!/usr/bin/env python3
"""Exercise the loaded G_EDIT fixture on the pinned GEM provider."""
import argparse
import json
from pathlib import Path

from build_c_program import build as application
from build_gem_desktop import build_desktop
from c_program import ABI
from gem_render_oracle import DESKTOP_PALETTE, font_bytes
from make_data_disk import make
from measure_mgview import expected
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def run(out, reuse=False):
    if reuse:
        program = read_build(out/'program')
        app = json.loads((out/'app/app.json').read_text())
        require(app['abi']==ABI, 'Stale edit object fixture ABI')
        require(sha256(out/'app/program.app')==app['sha256'], 'Changed edit object APP')
    else:
        app = application(out/'app',[ROOT/'tests/programs/mgedit_object.c'],minimum_stack=2560)
        program = build_desktop(out,source=ROOT/'tests/programs/c_mgedit.act',
            build_applications=False,program_output=out/'program',release_compiler=True,
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2)])
    media = out/'media'
    media.mkdir(exist_ok=True)
    (media/'EDITOBJ.APP').write_bytes((out/'app/program.app').read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
         binary_names={'EDITOBJ.APP'})

    font = font_bytes(out/'selected/src/vdi/font8x8.c')
    fill = bytes((b&254)+(b>>7) for b in DESKTOP_PALETTE[6:9])[::-1]
    cells = {name: next(d['address'] for d in program['image']['data']
                        if f'_CMGEDITTEST_{name.upper()}_' in d['name'])
             for name in ('round','base','checks')}
    record = dict(tier='development',status='running',app_bytes=app['bytes'],
                  abi=ABI['version'],pictures=[])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
            for key,value in PIN['configuration'].items():
                bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
            bridge.mount(0,str(out/'system.atr'))
            record['machine'] = verify_machine(bridge,ROM,PIN)

            def reach(condition):
                marker = program['labels']['native_cop']
                condition = f'(@xpc=${marker:x})&({condition})'
                bridge.bp_clear_all()
                bridge.bp_set(marker,condition=condition)
                stops = {program['labels'][name]: name for name in
                         ('heap_fault','stack_overflow','arithmetic_fault','done')}
                for stop in stops:
                    bridge.bp_set(stop)
                original = bridge.regs

                def regs():
                    state = original()
                    pc = bridge.eval_expr('@xpc')
                    if pc in stops:
                        record['stop'] = dict(name=stops[pc],checks=number(cells['checks']),
                                              round=number(cells['round']),registers=state)
                        raise RuntimeError(f'Edit object fixture reached {stops[pc]} before {condition}')
                    return state

                bridge.regs = regs
                try:
                    run_to(bridge,marker,condition=condition,timeout=120,frame_limit=8000)
                finally:
                    bridge.regs = original

            def number(address, size=2):
                return int.from_bytes(bridge.memdump(address,size),'little')

            def picture(addr, label, phase):
                def rect(name):
                    return [number(addr(name)+i*2) for i in range(4)]

                work = rect('work')
                x,y,width,height = work
                content = (b'Ax\n\tB\nSecond\nThird\nFourth\n' if phase==2
                           else b'A\tB\nSecond\nThird\nFourth\n')
                expected_pixels = expected(font,work,content,0)
                covered = phase==3
                if covered:
                    ox,oy,ow,oh = rect('coverBounds')
                    cx,cy,cw,ch = rect('coverWork')
                    # The frame projects a two-pixel physical shadow.
                    ow += 2
                    oh += 2
                path = out/(label+'.bgra')
                frame = bridge.rawscreen(str(path))
                pixels = path.read_bytes()
                checked = 0
                white,black = (bytes((b&254)+(b>>7) for b in DESKTOP_PALETTE[p:p+3])[::-1]
                               for p in (0,3))
                for row in range(height):
                    for column in range(width):
                        px,py = x+column,y+row
                        dest = (px+16)*4+py*frame.stride
                        source = (column+row*width)*3
                        wanted = expected_pixels[source:source+3]
                        if phase in (3,4):
                            inverted = row<32
                        else:
                            top = 8 if phase==2 else 0
                            inverted = column==0 and top<=row<top+8
                        if inverted:
                            wanted = black if wanted==white else white
                        if covered and ox<=px<ox+ow and oy<=py<oy+oh:
                            if not (cx<=px<cx+cw and cy<=py<cy+ch):
                                continue
                            wanted = fill
                        require(pixels[dest:dest+3]==wanted,
                                f'{label} pixel {px},{py} {pixels[dest:dest+3].hex()} != {wanted.hex()}')
                        checked += 1
                record['pictures'].append(dict(name=label,checked=checked))

            def before(_):
                for cycle in (1,2):
                    reach(f'(dw(${cells["round"]:x})={cycle})&(dw(${cells["checks"]:x})>={3+4*(cycle-1)})')
                    base = number(cells['base'],4)-(ABI['link_bank'] << 16)

                    def addr(name):
                        return base+app['image']['symbols'][name]

                    for phase in (1,2,3,4,5):
                        reach(f'(dw(${cells["round"]:x})={cycle})&(dw(${addr("phase"):x})={phase})')
                        reach(f'@frame>={bridge.eval_expr("@frame")+2}')
                        picture(addr,f'{cycle}-{phase}',phase)
                        bridge.poke16(addr('proceed'),phase)
                bridge.bp_clear_all()

            record['runtime'],_ = execute(bridge,program,before_run=before,timeout=180,frame_limit=16000)
            ownership(bridge,program,program['output'])
            record['checks'] = number(cells['checks'])
            require(record['checks']==12,'Incomplete edit object lifecycle')
        record['status']='pass'
    except Exception as error:
        record.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(),args.reuse)
