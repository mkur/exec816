#!/usr/bin/env python3
"""Replay cartridge boot against the matching, unchanged demo and its tests."""
import argparse
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(cartridge_build, demo_build, exec_source, output, variant, manual):
    # Published images use the tools from their release revision, including
    # historical stack placements. Do not reinterpret them with today's ABI.
    sys.path.insert(0, str(exec_source/'tools'))
    from native_program import require, sha256
    from os_boundary import run_to
    import banked_test_memory
    import test_demo
    from test_of816 import check_boot_guards, enter_forth, press, screen_text

    cart = json.loads((cartridge_build/'cartridge.json').read_text())
    boot = json.loads((demo_build/'of816/of816.json').read_text())
    require(cart['input_xex_sha256'] == boot['xex_sha256'], 'Cartridge and demo differ')
    image = cartridge_build/f'Exec-of816-atarimax-8mbit-{variant}.car'
    require(sha256(image) == cart['files'][image.name], 'Changed cartridge image')
    output.mkdir(parents=True, exist_ok=True)
    case_build = output/'demo'
    shutil.copytree(demo_build, case_build, dirs_exist_ok=True)
    labels = boot['labels']
    case = dict(status='running', tier='development', variant=variant,
                route='forth-command' if manual else 'autoboot', cartridge=cart,
                cartridge_sha256=sha256(image), observer_sha256=sha256(Path(__file__)),
                exec_revision=subprocess.check_output(
                    ['git','-C',str(exec_source),'rev-parse','HEAD'], text=True).strip())
    # The release's public walkthrough normally supplies its own XEX bootstrap.
    # Admit the cartridge bootstrap without altering any walkthrough assertions.
    # This exercises the documented public commands of the released preview.
    observer = inspect.getsource(test_demo.run)
    before = '    if showcase:\n'
    require(before in observer, 'Walkthrough observer entry changed')
    observer = observer.replace(before, '    if showcase and bootstrap is None:\n', 1)
    namespace = dict(vars(test_demo))
    exec(compile(observer,str(exec_source/'tools/test_demo.py'),'exec'),namespace)
    run_demo = namespace['run']
    case['walkthrough_observer'] = dict(source_sha256=sha256(exec_source/'tools/test_demo.py'),
                                      adjustment='Allow explicit bootstrap for showcase mode; assertions unchanged.')
    # Cartridge cold boot opens E: below $A000. The release's far-read helper
    # borrows $9000-$AFFF and requires MEMTOP >= $B000, so it cannot run here.
    # Inspect upper RAM through the debugger instead, without touching target
    # memory or changing the original cleanup and ownership assertions.
    original_read = banked_test_memory.read

    def read_memory(b, address, size, output):
        if address + size <= 65536:
            return b.memdump(address, size)
        data = b''.join((b.eval_expr(f'dw(${address+i:x})') & 65535).to_bytes(2, 'little')
                        for i in range(0, size, 2))
        return data[:size]

    case['walkthrough_observer']['upper_memory_reads'] = 'Debugger DW; no target scratch or execution'

    def bootstrap(b, program):
        b.boot(str(image))
        b.bp_set(labels['of_start'])
        b.bp_set(cart['labels']['cart_failed'])
        run_to(b, labels['of_start'], 4000, 90)
        b.bp_clear_all()
        require(b.peek16(cart['labels']['cart_segments']) == cart['segments'], 'Lost XEX segment')
        require(b.peek16(cart['labels']['cart_calls']) == cart['init_callbacks'], 'Lost INITAD call')
        require(b.memdump(cart['labels']['cart_remaining'],3) == bytes(3), 'Unread XEX bytes')
        require(b.peek(0x3fa) == b'\x01', 'Cartridge interlock not restored')
        # Writes at the former ROM window must now reach RAM.
        saved_window = b.memdump(0xa000,16)
        probe = bytes((i*29+7)&255 for i in range(16))
        b.memload(0xa000,probe)
        actual = b.memdump(0xa000,16)
        require(actual == probe, 'Cartridge is still mapped: '+str(dict(
            before=saved_window.hex(),after=actual.hex(),portb=b.peek(0xd301).hex(),
            trig3=b.peek(0xd013).hex(),configuration=b.config())))
        b.memload(0xa000,saved_window)
        saved = dict(vectors=b.memdump(0x256,9), iocb=b.memdump(0x340,32))
        screen = b.peek16(0x58)
        b._cmd_ok('KEY ALL up')
        if manual:
            case['cancel'] = enter_forth(b,labels,delay=240,key='RETURN')
            for ch in 'decimal 6 7 * .\n':
                press(b,labels,ch)
            require('42 ' in screen_text(b.memdump(screen,960)), 'Forth arithmetic failed')
            case['forth_result'] = 42
            b.screenshot(str(output/'forth.png'))
            for ch in 'exec816':
                press(b,labels,ch)
            press(b,labels,'\n',labels['of_handoff'])
        else:
            b.bp_set(labels['of_autoboot'])
            run_to(b,labels['of_autoboot'],1000,30)
            b.bp_clear_all()
            begin = b.eval_expr('@frame')
            b.bp_set(labels['of_handoff'])
            run_to(b,labels['of_handoff'],300,15)
            case['autoboot_frames'] = b.eval_expr('@frame')-begin
            require(249 <= case['autoboot_frames'] <= 251, 'Five-second autoboot changed')
        check_boot_guards(b,boot['layout'])
        case['of816_guards'] = 'intact'
        b.bp_clear_all()
        b.bp_set(program['labels']['start'])
        run_to(b,program['labels']['start'],1000,30)
        b.bp_clear_all()
        require(b.memdump(0x256,9) == saved['vectors'] and
                b.memdump(0x340,32) == saved['iocb'], 'OF816 handoff changed OS context')
        case['os_restored_at_handoff'] = True
        case['loader_callbacks'] = cart['init_callbacks']

    try:
        banked_test_memory.read = read_memory
        case['shell'] = run_demo(case_build, showcase=True, bootstrap=bootstrap,
                               media_path=demo_build/'of816'/boot['media']['name'])
        case['status'] = 'pass'
    except Exception as error:
        case.update(status='fail',error=str(error))
        raise
    finally:
        banked_test_memory.read = original_read
        (output/'results.json').write_text(json.dumps(case,indent=2)+'\n')
    return case


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cartridge-build',type=Path,required=True)
    parser.add_argument('--demo-build',type=Path,required=True)
    parser.add_argument('--exec-source',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--variant',choices=('old','new'),required=True)
    parser.add_argument('--manual',action='store_true')
    args = parser.parse_args()
    run(args.cartridge_build.resolve(),args.demo_build.resolve(),args.exec_source.resolve(),
        args.output.resolve(),args.variant,args.manual)
    print('Cartridge boot, OF816, disk commands, guards and EXIT passed:',args.variant,flush=True)
