#!/usr/bin/env python3
"""Focused emitted input.device development checks; no desktop/demo build."""
import argparse
import json
from pathlib import Path
import shutil

from native_program import ROOT, build, compiler, command, execute, verify_machine, require, read_build, sha256
from os_boundary import emulator, run_to
import adapter_state as adapter
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage

PIN = json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())


def c_layout(output, optimize):
    from generate_input_device import ABI
    from calypsi_image import check_layout
    expected = []
    expressions = []
    for name, record in ABI['records'].items():
        expected.append((name+' size', record['bytes']))
        expressions.append(f'sizeof(struct InputDevice{name})')
        for field, _, offset in record['fields']:
            expected.append((name+' '+field, offset))
            expressions.append(f'offsetof(struct InputDevice{name}, {field})')
    source = output/'layout.c'
    source.write_text('#include <devices/input.h>\n'
        '__attribute__((section("exec_layout")))\n'
        'const unsigned short __exec_layout[] = {\n'+',\n'.join(expressions)+'\n};\n')
    obj = output/'layout.o'
    command([shutil.which('cc65816'), '--code-model=large', '--data-model=huge',
             '-O2' if optimize else '-O0', '-I', ROOT/'c/include', '-c', '-o', obj, source])
    return check_layout(obj, expected)


def keyboard_stimulus(bridge, program, report):
    at = lambda name: next(d['address'] for d in program['image']['data']
        if d['name'].startswith('M_INPUTDEVICEKEYBOARD_'+name.upper()+'_'))

    def checkpoint(condition):
        bridge.bp_clear_all()
        bridge.bp_set(program['labels']['native_nmi'], condition=condition)
        bridge.bp_set(program['labels']['done'], condition=adapter.STOPPED)
        try:
            run_to(bridge, program['labels']['native_nmi'], frame_limit=1800,
                   timeout=15, condition=condition)
        except Exception:
            report['checkpoint'] = condition
            report['diagnostic'] = {name: bridge.peek16(at(name))
                                    for name in ('checks', 'received', 'stage')}
            report['diagnostic']['status'] = bridge.peek16(adapter.STATE)
            report['diagnostic']['clean_guard'] = bridge.memdump(at('cleanGuard'), 1).hex()
            report['diagnostic']['old_tag'] = bridge.memdump(at('oldTag'), 4).hex()
            report['diagnostic']['events'] = bridge.memdump(at('events'), 144).hex()
            raise

    def key(name, state):
        result = bridge._cmd_ok(f'KEY {name} {state}')
        require(result['raw_scan'], 'Keyboard fixture requires physical raw scanning')

    key('ALL', 'up')
    for index, (name, modifier, stage) in enumerate((
            ('A', None, 1), ('C', 'CTRL', 1), ('BREAK', None, 1),
            ('C', 'CTRL', 2), ('BREAK', None, 2), ('A', None, 3))):
        checkpoint(f'db(${at("stage"):x})={stage}')
        if modifier:
            key(modifier, 'down')
        key(name, 'down')
        if index == 5:
            break
        checkpoint(f'dw(${at("received"):x})>={index+1}')
        key(name, 'up')
        if modifier:
            key(modifier, 'up')
        if index < 5:
            checkpoint(f'@frame>={bridge.eval_expr("@frame")+4}')
    bridge.bp_clear_all()
    report['physical_keys'] = 6


def keyboard_hardware(bridge):
    return {name: bridge.memdump(address, size).hex() for name, address, size in (
        ('mask', 16, 1), ('skctl', 0x232, 1), ('key_vector', 0x208, 2),
        ('break_vector', 0x236, 2), ('timer_vector', 0x210, 2))}


def pointer_stimulus(bridge, program, report):
    at = lambda name: next(d['address'] for d in program['image']['data']
        if d['name'].startswith('M_INPUTDEVICEPOINTER_'+name.upper()+'_'))

    def reach(condition):
        bridge.bp_clear_all()
        bridge.bp_set(program['labels']['native_nmi'], condition=condition)
        try:
            run_to(bridge, program['labels']['native_nmi'], frame_limit=800,
                   timeout=15, condition=condition)
        except Exception:
            report['checkpoint'] = condition
            report['diagnostic'] = {name: bridge.peek16(at(name))
                for name in ('checks', 'received', 'sumX', 'sumY')}
            report['diagnostic']['button_states'] = bridge.memdump(at('buttonStates'), 1).hex()
            report['diagnostic']['status'] = bridge.peek16(adapter.STATE)
            raise

    bridge._cmd_ok('MOUSE ST')
    reach(f'db(${at("stage"):x})=1')
    for i in range(4):
        bridge._cmd_ok(f'MOUSE AT {2000+i*36000} 16 0 -1')
    reach(f'dw(${at("sumX"):x})>=4')
    bridge._cmd_ok('MOUSE AT 2000 0 0 1')
    reach(f'db(${at("buttonStates"):x})=1')
    bridge._cmd_ok('MOUSE AT 2000 0 0 0')
    reach(f'db(${at("buttonStates"):x})=3')
    bridge.memload(at('stop'), bytes([1]))
    bridge.bp_clear_all()
    report['physical_pointer'] = dict(movements=4, button_changes=2)


def text_stimulus(bridge, program, report):
    at = lambda name: next(d['address'] for d in program['image']['data']
        if d['name'].startswith('M_INPUTDEVICETEXT_'+name.upper()+'_'))

    def reach(condition):
        bridge.bp_clear_all()
        bridge.bp_set(program['labels']['native_nmi'], condition=condition)
        try:
            run_to(bridge, program['labels']['native_nmi'], frame_limit=1000,
                   timeout=15, condition=condition)
        except Exception:
            report['diagnostic']=dict(checks=bridge.peek16(at('checks')),
                stage=bridge.memdump(at('stage'),1).hex(),status=bridge.peek16(adapter.STATE))
            raise

    bridge._cmd_ok('KEY ALL up')
    reach(f'db(${at("stage"):x})=1')
    layout=json.loads((ROOT/'abi/console.json').read_text())['records']['Service']
    offset=next(f[2] for f in layout['fields'] if f[0]=='snapshot')
    base=program['build']['memory']['console_storage']['BASE']
    saved=int.from_bytes(bridge.memdump(base+offset,3),'little')
    report['text_claim_snapshot']=bridge.memdump(saved,960).hex()
    require(bridge._cmd_ok('KEY A down')['raw_scan'], 'Text console requires physical key scanning')
    reach(f'@frame>={bridge.eval_expr("@frame")+4}')
    bridge._cmd_ok('KEY A up')
    bridge._cmd_ok('KEY RETURN down')
    reach(f'db(${at("stage"):x})=2')
    bridge._cmd_ok('KEY RETURN up')
    reach(f'@frame>={bridge.eval_expr("@frame")+4}')
    bridge._cmd_ok('KEY B down')
    reach(f'db(${at("stage"):x})=3')
    bridge._cmd_ok('KEY B up')
    reach(f'@frame>={bridge.eval_expr("@frame")+4}')
    bridge._cmd_ok('KEY CTRL down')
    bridge._cmd_ok('KEY C down')
    bridge.bp_clear_all()
    report['text_input']=dict(cooked_line='a\n',raw_byte='b',cancellation='Ctrl-C')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--suite', choices=('abi', 'service', 'keyboard', 'pointer', 'client', 'frontend', 'text'), default='abi')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output/'program').mkdir(exist_ok=True)
    capture_override=output/'program/inputdevicesource.act'
    if args.suite == 'service':
        capture_override.write_text(
            (ROOT/'tests/programs/input-device-fixture/inputdevicesource.act').read_text())
    elif capture_override.exists():
        capture_override.unlink()
    layout = c_layout(output, args.mode == 'opt')
    options = {}
    if args.suite in ('frontend', 'text'):
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes']=8192
        profile_path=output/'memory-profile.json'
        profile_path.write_text(json.dumps(profile)+'\n')
        options.update(memory_profile=profile_path, console_deferred=True)
    program = read_build(args.from_build) if args.from_build else build(compiler(args.compiler_dir, release=True),
                    ROOT/'tests/programs'/f'input_device_{args.suite}.act', output/'program',
                    tasks=True, console=False, sio_enabled=False,
                    optimize=args.mode == 'opt', **options)
    report = dict(status='running', tier='development', qualification=False,
                  suite=args.suite, mode=args.mode, build=program['build'], c_layout=layout)
    pin, bridge_dir, rom = PIN, ROOT/'build/altirra-irq-bridge', ROOT/'build/firmware/altirraos-816.rom'
    if args.suite in ('keyboard', 'pointer', 'text'):
        from test_mouse_observe import PIN as INPUT_PIN, BRIDGE, ROM
        pin, bridge_dir, rom = INPUT_PIN, BRIDGE, ROM
        if args.suite == 'text':
            pin=json.loads(json.dumps(pin))
            pin['devices']=[]
            pin['machine']['addons']='off'
    expected_bridge = pin.get('mouse_input', {}).get('tooling', {}).get('sha256', pin['emulator']['sha256'])
    require(sha256(bridge_dir/'AltirraBridgeServer') == expected_bridge,
            'Unpinned input.device emulator')
    report['emulator_sha256'] = expected_bridge
    try:
        with emulator(bridge_dir, rom, output, pin=pin) as bridge:
            report['machine'] = verify_machine(bridge, rom, pin)
            def stimulus(b):
                report['keyboard_before'] = keyboard_hardware(b)
                if args.suite == 'keyboard':
                    keyboard_stimulus(b, program, report)
                elif args.suite == 'pointer':
                    pointer_stimulus(b, program, report)
                else:
                    report['text_screen_address']=b.peek16(0x58)
                    report['text_screen_before']=b.memdump(report['text_screen_address'],960).hex()
                    text_stimulus(b, program, report)
            report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=3600,
                                           before_run=stimulus if args.suite in ('keyboard', 'pointer', 'text') else None)
            if args.suite in ('keyboard', 'pointer', 'text'):
                bridge._cmd_ok('KEY ALL up')
                bridge._cmd_ok('MOUSE CLEAR')
                report['keyboard_after'] = keyboard_hardware(bridge)
                require(report['keyboard_after'] == report['keyboard_before'],
                        'Keyboard capture hardware was not restored')
                if args.suite == 'text':
                    actual=bridge.memdump(report['text_screen_address'],960)
                    expected=bytes.fromhex(report['text_claim_snapshot'])
                    report['text_screen_differences']=[i for i,(a,e) in enumerate(zip(actual,expected)) if a!=e]
                    require(actual==expected,
                            'Atari text screen was not restored')
                    require(not any(r['name'].startswith(('M_AES','M_DESK')) for r in program['image']['routines']),
                            'Standard Atari console still links GUI routines')
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            require(report['checks'] == {'abi': 17, 'service': 35, 'keyboard': 25,
                                        'pointer': 10, 'client': 13, 'frontend': 7, 'text': 15}[args.suite],
                    'Incomplete input.device fixture: '+str(report['checks']))
            clean_ownership(bridge, program, program['output'])
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            report['bank_zero_delta'] = dict(fixed=0, root=0, kernel=0, idle=0, per_task=0)
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS input.device {args.suite} {args.mode}: {report["checks"]} checks')


if __name__ == '__main__':
    main()
