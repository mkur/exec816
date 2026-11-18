#!/usr/bin/env python3
"""Open, edit, save, close and reopen the original-source MGEDIT APP."""
import argparse
import json
from pathlib import Path

from build_gem_desktop import build_desktop
from build_mgedit import build as editor
from build_mgview import build as viewer
from c_program import ABI
from filesystem_audit import Audit
from gem_render_oracle import font_bytes
from generate_aes_server import ABI as AES_ABI, expected_layout, layout
from make_data_disk import make
from measure_mgview import expected
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def run(out, reuse=False, short_save=False):
    if not reuse:
        editor(out/'app')
        viewer(out/'viewer')
        build_desktop(out, source=ROOT/'tests/programs/c_mgedit_document.act',
            build_applications=False, program_output=out/'program', release_compiler=True,
            task_capacity=12, system_mount='D1', dos_mounts=[dict(alias='D1', unit=49,
                sectors=2880, sector_bytes=256, profile=4, format=2, access='readwrite')])
    program = read_build(out/'program')
    folder = out/'app'
    if short_save:
        folder = out/'short-save'
        editor(folder, extra_sources=[ROOT/'tests/programs/mgedit_short_save.c'],
            definitions={str(ROOT/'c/runtime/files.c'):['-DEXEC_CRT_TEST']})
    folders = {'app':folder,'viewer':out/'viewer'}
    apps = {name:json.loads((path/'app.json').read_text()) for name,path in folders.items()}
    media = out/'media'
    media.mkdir(exist_ok=True)
    for group, name in (('app','MGEDIT.APP'),('viewer','MGVIEW.APP')):
        app = folders[group]/'program.app'
        require(apps[group]['abi']==ABI and apps[group]['sha256']==sha256(app), f'Stale {name}')
        (media/name).write_bytes(app.read_bytes())
    payload = b'MagiC\r\nExec\t6502\n\x80\x9b mixed bytes\r'
    big = payload*4 if short_save else (payload*2500)[:70000]
    small = b'Untouched\r\nsecond\tline\n'
    for name, data in (('BIG.TXT',big),('SMALL.TXT',small),('VIEW.TXT',b'Independent viewer\r\n')):
        (media/name).write_bytes(data)
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
         binary_names={path.name for path in media.iterdir()})

    symbols = json.loads((out/'c-image.json').read_text())['symbols']
    cells = {name:next(row['address'] for row in program['image']['data']
                      if f'_CMGEDITDOCUMENT_{name.upper()}_' in row['name'])
             for name in ('checks','phase','proceed','base','viewerBase','primary')}
    context_offsets = dict(expected_layout())
    wire = layout()
    report = dict(status='running',tier='development',checks=[])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for key, value in PIN['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.mount(0,str(out/'system.atr'))
            report['machine'] = verify_machine(b,ROM,PIN)

            def number(address, size=2):
                return int.from_bytes(b.memdump(address,size),'little')

            def reach(condition, limit=14000):
                marker = program['labels']['native_cop']
                condition = f'(@xpc=${marker:x})&({condition})'
                b.bp_clear_all()
                b.bp_set(marker,condition=condition)
                stops = {program['labels'][name]:name for name in
                         ('heap_fault','stack_overflow','arithmetic_fault','done')}
                for address in stops:
                    b.bp_set(address)
                original = b.regs

                def regs():
                    state = original()
                    pc = b.eval_expr('@xpc')
                    if pc in stops:
                        report['native_stop'] = dict(name=stops[pc], phase=number(cells['phase']),
                            primary=number(cells['primary'],4), checks=number(cells['checks']))
                        raise RuntimeError(f'Fixture reached {stops[pc]} before {condition}')
                    return state

                b.regs = regs
                try:
                    run_to(b,marker,condition=condition,timeout=220,frame_limit=limit)
                finally:
                    b.regs = original

            def frames(count):
                reach(f'@frame>={b.eval_expr("@frame")+count}')

            def key(name, control=False):
                if control:
                    b._cmd_ok('KEY CTRL down')
                    frames(3)
                b._cmd_ok(f'KEY {name} down')
                frames(3)
                b._cmd_ok(f'KEY {name} up')
                if control:
                    b._cmd_ok('KEY CTRL up')
                frames(6)

            def symbol(group, base, name):
                return base+apps[group]['image']['symbols'][name]-(ABI['link_bank']<<16)

            def phase(n):
                reach(f'dw(${cells["phase"]:x})={n}')

            def open_windows(table,count):
                reach(f'dw(${table+4*(count-1):x})!=0')
                frames(16)
                return [number(table+4*i,4) for i in range(count)]

            def context():
                for i in range(AES_ABI['constants']['CONTEXTS']):
                    address = number(symbols['contexts']+4*i,4)
                    if address and number(address+context_offsets['C context multiline'],4):
                        return address
                raise RuntimeError('Missing native editor context')

            def top(handle, address):
                for _ in range(6):
                    if number(address)==handle:
                        return
                    key('TAB',control=True)
                    frames(20)
                raise RuntimeError(f'Could not raise window {handle}, top is {number(address)}')

            def prompt(form):
                key('U',control=True)
                reach(f'dw(${form:x})!=0',limit=500)
                frames(12)

            def check_redraw(aes, handle):
                views = aes+context_offsets['C context views']
                fields = wire['WindowView']['fields']
                for slot in range(AES_ABI['constants']['WINDOWS']):
                    view = number(views+4*slot,4)
                    if view and number(view+fields['handle'])==handle:
                        break
                else:
                    raise RuntimeError('Missing editor window view')
                work = view+fields['work']
                x,y = number(work),number(work+2)
                pixels = expected(font_bytes(out/'selected/src/vdi/font8x8.c'),
                    (x,y,40,8),b'MagiC',0)
                path = out/'editor-exposed.bgra'
                screen = b.rawscreen(str(path))
                raw = path.read_bytes()
                # The caret owns the first column of the first character.
                for row in range(8):
                    for col in range(1,40):
                        at = (y+row)*screen.stride+(x+col+16)*4
                        want = (row*40+col)*3
                        require(raw[at:at+3]==pixels[want:want+3],
                                f'Editor exposure pixel {col},{row} differs')

            def exercise(_):
                phase(1)
                view_table = symbol('viewer',number(cells['viewerBase'],4),'windows')
                viewed, = open_windows(view_table,1)
                # The pinned MGVIEW WINDOW starts with its GEM WORD handle.
                viewer_handle = number(viewed)
                b.poke16(cells['proceed'],1)
                phase(2)
                table = symbol('app',number(cells['base'],4),'windows')
                first, second = open_windows(table,2)
                aes = context()
                directory = number(aes+wire['Request']['fields']['directory'],3)
                focused = directory+wire['Directory']['fields']['topWindow']
                form = aes+context_offsets['C context form']
                top(viewer_handle,focused)
                top(number(first),focused)
                check_redraw(aes,number(first))
                report['checks'].append('two editor windows, viewer focus and exposure pixels')

                key('X')
                reach(f'dw(${first+2:x})=1',limit=500)
                prompt(form)
                key('ESC')
                reach(f'dw(${form:x})=0',limit=500)
                require(number(table,4)==first and number(first+2)==1,
                        'Dismissal lost the dirty document')
                report['checks'].append('cancel keeps the document dirty and open')

                if short_save:
                    flag = symbol('app',number(cells['base'],4),'shortSave')
                    prompt(form)
                    b.poke16(flag,1)
                    key('RETURN')
                    reach(f'dw(${flag:x})=2')
                    reach(f'dw(${form:x})!=0')
                    frames(12)
                    require(number(table,4)==first and number(first+2)==1,
                            'Short save closed the document or cleared its dirty flag')
                    b.poke16(flag,0)
                    key('RETURN')
                    reach(f'dw(${form:x})=0',limit=500)
                    report['checks'].append('short write keeps the dirty document open')

                prompt(form)
                key('RETURN')
                reach(f'dw(${table:x})=0')
                report['checks'].append('save on close')

                top(number(second),focused)
                key('Z')
                reach(f'dw(${second+2:x})=1',limit=500)
                prompt(form)
                key('TAB')
                key('SPACE')
                phase(3)
                report['checks'].append('discard on close')

                reopened, = open_windows(table,1)
                aes = context()
                edit = number(aes+context_offsets['C context multiline'],4)
                buffer = number(edit+4,4)
                require(b.memdump(buffer,8)==b'x'+big[:7] and number(edit+12,4)==len(big)+1,
                        'Reopened document differs from saved edit')
                key('U',control=True)
                phase(4)
                report['checks'].append('reopen exact edit and retire both lifetimes')
                b.bp_clear_all()

            report['runtime'],_ = execute(b,program,before_run=exercise,timeout=240,frame_limit=20000)
            ownership(b,program,program['output'])
            require(number(cells['checks'])==16,'Incomplete document and viewer lifecycle')
            b._cmd_ok('EJECT drive=0')
        disk = Audit((out/'system.atr').read_bytes())
        disk.sdfs()
        require(disk.files['BIG.TXT']==b'x'+big and disk.files['SMALL.TXT']==small,
                'The on-disk bytes differ after Save and Discard')
        report.update(status='pass',saved_bytes=len(big)+1,editor_app_bytes=apps['app']['bytes'])
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        name = 'results-short.json' if short_save else 'results.json'
        (out/name).write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--short-save', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(),args.reuse,args.short_save)
