#!/usr/bin/env python3
"""Exercise real Forth input, ROM coexistence and the one-way Exec handoff."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_calypsi import LINES, PROMPT
from test_console_display import glyph
from test_dos_stack import execute
from test_heap_api import clean_ownership
from test_shell_core import KEYS

KEYS = {**KEYS, '@':('8',True), '!':('1',True)}

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def screen_text(raw):
    return ''.join(chr((value & 127)+32 if (value & 127) < 64 else value & 127) for value in raw)


def check_boot_guards(bridge, layout):
    guards = [layout['OF_STACK']-16, layout['OF_STACK']+1536, layout['OF_STACK']+512,
              layout['OF_ADAPTER']-16, layout['OF_ADAPTER']+1536, layout['OF_ADAPTER']+0x4f0]
    for address in guards:
        require(bridge.memdump(address,16) == bytes([0xa5])*16, f'OF guard changed: ${address:x}')
    for address in (layout['OF_DATA'], layout['OF_DATA']+0xfff0):
        require(all(bridge.eval_expr(f'dw(${address+i:x})') == 0xa5a5 for i in range(0,16,2)),
                'Forth data-space guard changed')


def press(bridge, labels, character, target=None):
    name,shift = KEYS[character]
    bridge.bp_clear_all()
    target = target or labels['of_wait_key']
    previous = bridge.peek16(labels['of_keys'])
    condition = f'dw(${labels["of_keys"]:x})>{previous}'
    bridge.bp_set(target,condition=condition)
    if shift:
        bridge._cmd_ok('KEY SHIFT down')
    require(bridge._cmd_ok(f'KEY {name} down')['raw_scan'], 'Physical key delivery required')
    run_to(bridge,target,3000,60,condition)
    bridge._cmd_ok(f'KEY {name} up')
    if shift:
        bridge._cmd_ok('KEY SHIFT up')
    bridge.bp_clear_all()
    if target == labels['of_wait_key']:
        # Let the ROM see key release while blocked in K: input.
        bridge.frame(2)
        bridge.pause()


def enter_forth(bridge, labels, delay=0, key='X', hold=2):
    """Cancel with physical input, consuming even a held/repeating key."""
    bridge.bp_clear_all()
    bridge._cmd_ok('KEY ALL up')
    bridge.bp_set(labels['of_autoboot_wait'])
    run_to(bridge,labels['of_autoboot_wait'],1000,30)
    bridge.bp_clear_all()
    if delay:
        bridge.frame(delay)
        bridge.pause()
    require(bridge.peek16(labels['of_phase']) == 1, 'Autoboot ended before cancellation')
    seconds = bridge.peek16(labels['of_seconds'])
    require(bridge._cmd_ok(f'KEY {key} down')['raw_scan'], 'Physical cancel key required')
    bridge.frame(hold)
    bridge.pause()
    bridge._cmd_ok(f'KEY {key} up')
    bridge.bp_set(labels['of_wait_key'])
    run_to(bridge,labels['of_wait_key'],120,15)
    bridge.bp_clear_all()
    require(bridge.peek16(labels['of_keys']) == 0 and bridge.peek(0x2fc) == b'\xff',
            'Cancel key leaked into the Forth input line')
    # Crossing the original deadline must not restart the countdown.
    bridge.frame(260)
    bridge.pause()
    require(bridge.peek16(labels['of_phase']) == 1, 'Cancelled autoboot still entered Exec')
    return dict(key=key,delay_frames=delay,held_frames=hold,seconds_remaining=seconds,
                cancelled=True,key_consumed=True,stays_in_forth=True)


def check_autoboot(output, record, program, wrap=False):
    """No input must reach the ordinary loader after five PAL seconds."""
    labels = record['labels']
    case = 'autoboot-clock-wrap' if wrap else 'autoboot'
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom',
                  output/case,pin=PIN) as bridge:
        bridge.boot(str(output/'Exec-of816.xex'))
        bridge.bp_set(labels['of_start'])
        run_to(bridge,labels['of_start'],3000,90)
        bridge.bp_clear_all()
        saved = dict(vectors=bridge.memdump(0x256,9),iocb=bridge.memdump(0x340,32))
        bridge._cmd_ok('KEY ALL up')
        if wrap:
            bridge.poke(0x14,240)
        bridge.bp_set(labels['of_autoboot'])
        run_to(bridge,labels['of_autoboot'],1000,30)
        bridge.bp_clear_all()
        start_frame = bridge.eval_expr('@frame')
        clock = bridge.peek(0x14)
        bridge.bp_set(labels['of_handoff'])
        run_to(bridge,labels['of_handoff'],300,15)
        elapsed = bridge.eval_expr('@frame')-start_frame
        require(249 <= elapsed <= 251, f'Autoboot delay was {elapsed} PAL frames, expected 250')
        require(bridge.peek16(labels['of_seconds']) == 0, 'Countdown did not expire')
        require(bridge.peek16(labels['of_keys']) == 0, 'Automatic boot required input')
        text = screen_text(bridge.memdump(bridge.peek16(88),960))
        require('Exec816 in: 5 4 3 2 1' in text, 'Missing visible countdown')
        if wrap:
            require(bridge.peek(0x14) < clock, 'Clock wrap case did not wrap')
        check_boot_guards(bridge,record['layout'])
        bridge.bp_clear_all()
        bridge.bp_set(program['labels']['start'])
        run_to(bridge,program['labels']['start'],3000,60)
        require(bridge.memdump(0x256,9) == saved['vectors'] and
                bridge.memdump(0x340,32) == saved['iocb'], 'Autoboot did not restore OS state')
        require(bridge.peek16(labels['of_phase']) == 2, 'Automatic handoff did not run')
    return dict(case=case,status='pass',frames=elapsed,seconds=elapsed/50,
                clock_wrap=wrap,guards='intact',os_restored=True)


def check_exit(output, record, busy=False):
    """BYE and an occupied IOCB leave the OS usable without entering Exec."""
    labels = record['labels']
    case = 'occupied-iocb' if busy else 'bye'
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom',
                  output/case,pin=PIN) as bridge:
        bridge.boot(str(output/'Exec-of816.xex'))
        bridge.bp_set(labels['of_start'])
        run_to(bridge,labels['of_start'],3000,90)
        bridge.bp_clear_all()
        if busy:
            bridge.poke(0x350,0)  # read-only admission check must leave this row alone
        vectors = bridge.memdump(0x256,9)
        iocb = bridge.memdump(0x340,32)
        memlo = bridge.peek16(record['layout']['EXEC_OLD_MEMLO'])
        if busy:
            bridge.bp_set(labels['of_park'])
            run_to(bridge,labels['of_park'],1000,30)
        else:
            cancel = enter_forth(bridge,labels,delay=240,key='RETURN')
            require(cancel['seconds_remaining'] == 1, 'Late cancellation missed the final second')
            for character in 'bye':
                press(bridge,labels,character)
            press(bridge,labels,'\n',labels['of_park'])
        require(bridge.memdump(0x256,9) == vectors and bridge.memdump(0x340,32) == iocb,
                'Monitor exit did not restore vectors/IOCBs')
        require(bridge.peek16(0x2e7) == memlo, 'Monitor exit did not restore MEMLO')
        clock = bridge.memdump(18,3)
        bridge.bp_clear_all()
        bridge.frame(3)
        bridge.pause()
        require(bridge.memdump(18,3) != clock, 'OS VBI stopped after monitor exit')
    result = dict(case=case,status='pass',os_restored=True)
    if not busy:
        result['cancel'] = cancel
    return result


def run(output):
    record = json.loads((output/'of816.json').read_text())
    xex = output/'Exec-of816.xex'
    require(sha256(xex) == record['xex_sha256'], 'OF816 bundle changed')
    for name,digest in record['inputs'].items():
        require(sha256(ROOT/name) == digest, 'Boot source changed: '+name)
    program = read_build(Path(record['exec_build']))
    require(program['build']['xex_sha256'] == record['exec_xex_sha256'], 'Embedded Exec image changed')
    labels = record['labels']
    bridge_dir = ROOT/'build/shell-paced-bridge'
    rom = ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Wrong emulator')
    require(sha256(rom) == PIN['rom']['sha256'], 'Wrong ROM')
    if record.get('media'):
        from test_of816_shell import run as run_shell
        return run_shell(output,record,program)
    require(program['build'].get('foreign_image',{}).get('format') == 'calypsi65816-standalone-v1',
            'This smoke runner expects the standard shell or Calypsi message example')
    report = dict(status='running',tier='development',boot=record,pin=PIN,
                  observer_sha256=sha256(Path(__file__)))
    try:
        with emulator(bridge_dir,rom,output,pin=PIN) as b:
            report['machine'] = verify_machine(b,rom,PIN)
            b.boot(str(xex))
            b.bp_set(labels['of_start'])
            run_to(b,labels['of_start'],3000,90)
            b.bp_clear_all()
            saved = dict(vectors=b.memdump(0x256,9), iocb=b.memdump(0x340,32))
            screen = b.peek16(88)
            report['cancel'] = enter_forth(b,labels,hold=60)
            require(b.peek16(labels['of_phase']) == 1, 'Forth did not initialize')
            check_boot_guards(b,record['layout'])
            require('OF816 by M.G.' in screen_text(b.memdump(screen,960)), 'Missing Forth banner')

            def line(command):
                for character in command+'\n':
                    press(b,labels,character)
                return screen_text(b.memdump(screen,960))

            text = line('decimal 6 7 * .')
            require('42 ' in text, 'Forth arithmetic failed')
            text = line(': square dup * ; 9 square .')
            require('81 ' in text, 'Compiled Forth definition failed')
            text = line('0 5000 0 do i - loop negate .')
            require('12497500 ' in text, 'Forth loop failed')
            require(b.peek16(labels['of_nmis']) > 0, 'No native VBI in Forth')
            (output/'forth.screen.bin').write_bytes(b.memdump(screen,960))
            b.screenshot(str(output/'forth.png'))
            report['forth'] = dict(arithmetic=42,definition=81,loop=12497500,
                                   native_nmis=b.peek16(labels['of_nmis']),native_irqs=b.peek16(labels['of_irqs']))
            for character in 'exec816':
                press(b,labels,character)
            press(b,labels,'\n',labels['of_handoff'])
            check_boot_guards(b,record['layout'])
            report['forth']['guards'] = 'intact'
            b.bp_clear_all()
            b.bp_set(program['labels']['start'])
            run_to(b,program['labels']['start'],3000,60)
            b.bp_clear_all()
            require(b.memdump(0x256,9) == saved['vectors'], 'Firmware vectors survived handoff')
            require(b.memdump(0x340,32) == saved['iocb'], 'Firmware IOCB survived handoff')
            require(b.peek16(labels['of_phase']) == 2, 'Exec handoff did not run')
            saved.update(screen=b.memdump(screen,960),cursor=b.peek(752),mask=b.peek(16))

            def before_exec(bridge):
                prompt = screen+len(LINES)*40
                condition = '&'.join(f'db(${prompt+i:x})={glyph(ord(c))}' for i,c in enumerate(PROMPT))
                marker = program['labels']['native_nmi']
                bridge.bp_set(marker,condition=condition)
                run_to(bridge,marker,3000,90,condition)
                # Wait for ANTIC to render the already-verified cells before
                # recording a screenshot; the NMI entry can precede that frame.
                bridge.bp_clear_all()
                condition += f'&(@frame>={bridge.eval_expr("@frame")+2})'
                bridge.bp_set(marker,condition=condition)
                run_to(bridge,marker,120,15,condition)
                physical = bridge.memdump(screen,960)
                for row,value in enumerate(LINES):
                    require(physical[row*40:row*40+len(value)] == bytes(map(glyph,value.encode())),
                            'Exec C message output differs')
                (output/'exec.screen.bin').write_bytes(physical)
                bridge.screenshot(str(output/'exec.png'))
                bridge.bp_clear_all()
                capture = program['build']['memory']['console_storage']['CAPTURE']
                previous = bridge.eval_expr(f'dw(${capture+10:x})')
                require(bridge._cmd_ok('KEY RETURN down')['raw_scan'], 'Physical Return required')
                condition = f'dw(${capture+10:x})>{previous}'
                bridge.bp_set(marker,condition=condition)
                run_to(bridge,marker,120,15,condition)
                bridge._cmd_ok('KEY RETURN up')
                bridge.bp_clear_all()

            runtime,_ = execute(b,program,preloaded=True,before_run=before_exec,frame_limit=3000,timeout=90)
            report['runtime'] = runtime
            require(runtime['created'] == 2 and runtime['os_calls'] == 0, 'Wrong Exec Task/console flow')
            require(b.memdump(screen,960) == saved['screen'] and b.peek(752) == saved['cursor'] and
                    b.peek(16) == saved['mask'], 'Exec OS restoration failed')
            clean_ownership(b,program,program['output'])
            report['output'] = list(LINES)
        report['exit_cases'] = [check_exit(output,record),check_exit(output,record,busy=True)]
        report['autoboot'] = [check_autoboot(output,record,program),
                             check_autoboot(output,record,program,wrap=True)]
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/demo/of816')
    args = parser.parse_args()
    run(args.output.resolve())
    print('OF816 to Exec816 handoff passed')
