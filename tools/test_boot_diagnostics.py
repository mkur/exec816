#!/usr/bin/env python3
"""Focused packaged boots: both VBXE pages, FX 1.24, quiet/error output, bank $01."""
import argparse
import copy
import json
import time
from pathlib import Path

from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_mouse_observe import BRIDGE, ROM
from test_shell_core import KEYS
from test_of816 import enter_forth, press
from generate_console import constants as console_constants

CASES = (('d600-126',False,126,1),('d700-124',True,124,1),
         ('quiet-d700',True,124,0),('absent-quiet',None,126,0))


def os_text(bridge):
    screen = bridge.memdump(bridge.peek16(0x58), 960)
    def character(value):
        value &= 127
        return chr(value+32 if value < 64 else value)
    return '\n'.join(''.join(map(character, screen[n:n+40])).rstrip()
                     for n in range(0, 960, 40))


def reach(bridge, address, timeout=180):
    bridge.bp_set(address & 0xffff,condition=f'@xpc=${address:x}')
    return run_to(bridge, address & 0xffff, frame_limit=16000, timeout=timeout,
                  condition=f'@xpc=${address:x}')


def rendezvous(bridge, program, condition):
    bridge.bp_clear_all()
    marker = program['labels']['native_nmi']
    condition = f'(@xpc=${marker:x})&({condition})'
    bridge.bp_set(marker,condition=condition)
    return run_to(bridge,marker,frame_limit=12000,timeout=180,condition=condition)


def type_command(bridge, text):
    for character in text:
        key, shifted = KEYS[character]
        if shifted:
            bridge._cmd_ok('KEY SHIFT down')
        bridge._cmd_ok('KEY '+key+' down')
        bridge.resume()
        time.sleep(.06)
        bridge.pause()
        bridge._cmd_ok('KEY '+key+' up')
        if shifted:
            bridge._cmd_ok('KEY SHIFT up')
        bridge.resume()
        time.sleep(.06)
        bridge.pause()
    bridge._cmd_ok('KEY RETURN down')
    bridge.resume()
    time.sleep(.06)
    bridge.pause()
    bridge._cmd_ok('KEY RETURN up')
    bridge.bp_clear_all()


def run(bundle, output, selected=None):
    bundle, output = bundle.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    program = read_build(bundle)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    monitor = json.loads((bundle/'of816/of816.json').read_text())
    memory = program['build']['memory']
    shell = next(d['address'] for d in program['image']['data']
                 if '_SHELLAPP_SHELL_' in d['name'])
    console = console_constants()
    sentinel = bytes((i*37+11) & 255 for i in range(65536))
    report = dict(status='running', tier='development', build=program['build'],
                  xex_sha256=sha256(bundle/'of816/Exec-of816.xex'), cases=[],
                  inputs={name:sha256(ROOT/name) for name in (
                      'tools/test_boot_diagnostics.py','platform/altirraos/hosted.s',
                      'platform/altirraos/boot-diagnostics.s','platform/altirraos/blitter.s',
                      'platform/altirraos/vbxe-map.s','platform/altirraos/vbxe.c',
                      'platform/of816/platform-words.s','platform/altirraos/memory-4m.json')})
    try:
        for name, alternate, version, verbose in CASES:
            if selected and name not in selected:
                continue
            folder = output/name
            pin = copy.deepcopy(manifest['pin'])
            if alternate is None:
                pin['devices'] = []
                pin['machine']['addons'] = 'off'
            else:
                device = pin['devices'][0]
                device['settings'].update(alt_page=alternate, version=version)
                device['register_base'] = 0xd700 if alternate else 0xd600
                device['readback'] = [dict(address=device['register_base']+0x40,
                                          bytes=[0x10, 0x24 if version == 124 else 0x26])]
            case = dict(name=name, pin=pin, status='running')
            report['cases'].append(case)
            print(name,'booting',flush=True)
            with emulator(BRIDGE, ROM, folder, pin=pin) as bridge:
                case['machine'] = verify_machine(bridge, ROM, pin)
                for key, value in manifest['configuration'].items():
                    bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
                bridge.mount(0, str(bundle/'system.atr'))
                bridge.mount(7, str(bundle/'work.atr'))
                bridge.boot(str(bundle/'of816/Exec-of816.xex'))
                # Stop after OS boot/setup, before OF816 and kernel payload loading.
                reach(bridge, program['labels']['loader_of_begin'])
                print(name,'loader ready',flush=True)
                bridge.memload(0x10000, sentinel)
                bridge.bp_clear_all()
                settings = None
                if name=='quiet-d700':
                    labels = monitor['labels']
                    reach(bridge,labels['of_start'])
                    enter_forth(bridge,labels,key='RETURN')
                    flag = memory['boot_config']['address']+7
                    for command, expected in (('BOOT-VERBOSE@ .',1),
                            ('0 BOOT-VERBOSE! BOOT-VERBOSE@ .',0),
                            ('2 BOOT-VERBOSE!',0),('65536 BOOT-VERBOSE!',0),
                            ('1 BOOT-VERBOSE!',1),('0 BOOT-VERBOSE!',0)):
                        for character in command+'\n':
                            press(bridge,labels,character)
                        require(bridge.memdump(flag,1)==bytes([expected]),
                                'Forth verbosity setter failed: '+command)
                    settings = bridge.memdump(memory['boot_config']['address'],8)
                    for character in 'EXEC816':
                        press(bridge,labels,character)
                    press(bridge,labels,'\n',labels['of_handoff'])
                reach(bridge, program['labels']['loader_start'])
                bridge.bp_clear_all()
                reach(bridge, program['labels']['start'])
                print(name,'native entry',flush=True)
                if settings is not None:
                    require(bridge.memdump(memory['boot_config']['address'],8)==settings,
                            'Resumed loading overwrote the verbosity setting')
                    case['forth_settings_preserved'] = True
                else:
                    bridge.poke(memory['boot_config']['address']+7, verbose)
                bridge.bp_clear_all()
                if alternate is None:
                    reach(bridge, program['labels']['done'])
                    text = os_text(bridge)
                    require('CONSOLE FAILED=$F731' in text,
                            'Quiet boot hid the console failure: '+text)
                    require('System halted: $F731' in text,
                            'Quiet boot hid the fatal startup code: '+text)
                    require('BOOT MEMLO' not in text, 'Quiet mode printed the boot trace')
                    require(bridge.peek16(memory['adapter_state']['STATUS']) == 0xf731,
                            'Unexpected failure status')
                    bridge.screenshot(str(folder/'diagnostics.png'))
                else:
                    if verbose:
                        # The bridge only supports bank-zero PC breakpoints.
                        # Stop at the worker-ready trace's ROM gateway, before
                        # the C driver activates the bitmap display.
                        marker = program['labels']['native_cop']
                        condition = '(db($342)=11)&(dw(dw($344))=$4f43)&(dw(dw($344)+2)=$534e)'
                        bridge.bp_set(marker,condition=condition)
                        run_to(bridge,marker,frame_limit=12000,timeout=180,condition=condition)
                        bridge.screenshot(str(folder/'diagnostics.png'))
                    else:
                        rendezvous(bridge,program,f'(dw(${shell:x})!=0)|(db(${shell+2:x})!=0)')
                    print(name,'console initialization',flush=True)
                    text = os_text(bridge)
                    base = '$D700' if alternate else '$D600'
                    if verbose:
                        require('BOOT MEMLO    =' in text and 'RAM ADOPT     =OK' in text
                                and 'TASK/HEAP INIT=OK' in text
                                and text.count('RAM ADOPT     =') == 1
                                and text.count('TASK/HEAP INIT=') == 1,
                                'Missing kernel diagnostics: '+text)
                        require('VBXE BASE     ='+base in text and
                                ('VBXE rev      =1.24a' if version == 124 else 'VBXE rev      =1.26a') in text,
                                'Wrong hardware report: '+text)
                    else:
                        require('BOOT MEMLO' not in text and 'VBXE rev      =' not in text,
                                'Quiet mode printed diagnostics')
                    bridge.bp_clear_all()
                    rendezvous(bridge,program,f'(dw(${shell:x})!=0)|(db(${shell+2:x})!=0)')
                    pointer = lambda at:int.from_bytes(bridge.memdump(at,3),'little')
                    windows = program['build']['memory']['console_storage']['WINDOWS']
                    top = pointer(windows+console['WINDOWS_ITEMS']+console['WINDOW_INSTANCE'])
                    read_ready = top+console['INSTANCE_READREADY']
                    rendezvous(bridge,program,f'db(${read_ready:x})=2')
                    dos = program['build']['memory']['dos_storage']['BASE']
                    scope = pointer(pointer(dos)+83)
                    require(scope!=0,'Shell did not publish its foreground scope')
                    ready = f'(db(${read_ready:x})=2)&(db(${scope+54:x})=0)'
                    rendezvous(bridge,program,ready)
                    print(name,'shell ready',flush=True)
                    mailbox = program['build']['task_storage']['BLITTER_STATE']
                    before = int.from_bytes(bridge.memdump(mailbox+20,4),'little')
                    tag = bridge.peek16(scope+14)
                    bridge.bp_clear_all()
                    type_command(bridge,'cat sys:story.txt')
                    rendezvous(bridge,program,ready+f'&(dw(${scope+14:x})>{tag})')
                    after = int.from_bytes(bridge.memdump(mailbox+20,4),'little')
                    require(after > before, 'Command did not exercise asynchronous scrolling')
                    require(bridge.peek16(mailbox+34) == (0x100 if alternate else 0),
                            'IRQ handler selected the wrong VBXE page')
                    case['scroll_operations'] = after-before
                    bridge.screenshot(str(folder/'shell.png'))
                require(bridge.memdump(0x10000,65536) == sentinel, 'Exec changed bank $01')
                table = memory['constants']['TABLE']
                require(bridge.memdump(table+4,4) == bytes([2,0,1,0]),
                        'Bank $01 lost its firmware reservation')
                require(bridge.peek16(memory['constants']['ADOPTED']) == 1,
                        'Memory adoption failed')
                case.update(status='pass', diagnostics=text, bank_one='unchanged')
            print(name, 'passed', flush=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=[case[0] for case in CASES],action='append')
    args = parser.parse_args()
    run(args.bundle,args.output,args.case)
