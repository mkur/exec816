#!/usr/bin/env python3
"""Source-qualified producer admission, signal retention and retirement."""
import argparse
import json
from pathlib import Path

from generate_tasks import ABI
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from stack_budget import stack_usage
from test_cooperative import data
from test_heap_api import clean_ownership
PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

CASES = {'lifetime': 0, 'target-removal': 1, 'controller-removal': 2,
         'active-signal': 3, 'released-signal': 4, 'wrong-release': 5,
         'wrong-drain': 6, 'recipient-release': 7, 'independent-sources': 8}


def run(output, mode, selected=None, replay=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pin=PIN
    bridge=ROOT/'build/shell-paced-bridge'
    if selected is None or any(name.startswith('blitter-') for name in selected):
        from test_mouse_observe import PIN as BLITTER_PIN, BRIDGE
        pin=BLITTER_PIN;bridge=BRIDGE
    report = dict(status='running', tier='development', mode=mode, cases=[])
    try:
        require(sha256(bridge/'AltirraBridgeServer') == (pin['mouse_input']['tooling']['sha256'] if 'mouse_input' in pin else pin['emulator']['sha256']),
                'Unpinned producer emulator')
        program = read_build(output/'program') if replay else build(compiler(ROOT/'build/actionc'),
            ROOT/'tests/programs/producer_lifetime.act', output/'program', optimize=mode=='opt',
            tasks=True, task_capacity=8, console=False, console_test=True)
        require(program['build']['optimize'] == (mode=='opt'), 'Wrong compiler mode')
        memory = program['build']['memory']
        baseline = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget', 'task_pools', 'runtime_reservations', 'phase_reservations'):
            require(memory[key] == baseline[key], 'Producer changed '+key)
        report.update(build=program['build'], pin=pin, harness_sha256=sha256(Path(__file__)),
            xex_sha256=sha256(program['xex']), producer_imports=ABI['producer_imports'],
            bank_zero_delta=dict(fixed=0, per_task=[0]*8, private_idle=0))
        specs = [(prefix+'-'+name, source, kind) for prefix, source in [('serial',1), ('keyboard',2), ('pointer',3), ('blitter',4)]
                 for name, kind in CASES.items()]+[('old-profile', 0, 9)]
        if selected:
            require(set(selected) <= {s[0] for s in specs}, 'Unknown producer case')
            specs = [s for s in specs if s[0] in selected]
        with emulator(bridge, ROOT/'build/firmware/altirraos-816.rom', output, pin=pin) as b:
            report['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', pin)
            for number, (name, source, kind) in enumerate(specs):
                folder = output/name
                folder.mkdir(exist_ok=True)
                if number:
                    b.state_load(slot='loaded')
                result = dict(name=name, status='running')
                report['cases'].append(result)

                def before(bridge):
                    if not number:
                        bridge.state_save(slot='loaded')
                    at = lambda name: next(d['address'] for d in program['image']['data'] if '_'+name.upper()+'_' in d['name'])
                    bridge.memload(at('source'), source.to_bytes(2,'little'))
                    bridge.poke(at('kind'), kind)
                    if kind == 9:
                        # A valid stack extent with unsupported source zero.
                        # Accepting the old profile would return normally;
                        # profile rejection must fault before admission.
                        code = bytes.fromhex('c2303b38e90a001ba9000083013b1aaa')
                        code += bytes([0xa0,0,6,0xa9,ABI['services']['BIND_PRODUCER'],0,0x02,0x50])
                        code += bytes.fromhex('3b18690a001b6b')
                        bridge.memload(program['image']['entry'], code)
                        result['old_profile_probe'] = code.hex()

                fault = kind not in (0,7)
                runtime, _ = execute(b, {**program,'output':folder}, before_run=before,
                    preloaded=bool(number), expected_status=4 if fault else 0,
                    frame_limit=3000, timeout=120)
                result.update(runtime=runtime, checks=data(b,program['image'],'checks',True)[0],
                              stack_usage=stack_usage(b,memory))
                if fault and kind != 9:
                    require(data(b,program['image'],'checkpoint') == [kind], 'Wrong rejection point')
                if not fault:
                    require(data(b,program['image'],'finished') == [1], 'Recipient not retired')
                    clean_ownership(b,program,program['output'])
                require(all(v['remaining_above_floor']>0 for v in result['stack_usage'].values()), 'Stack floor reached')
                result['status'] = 'pass'
                print(mode,name,'pass',flush=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        if report['cases']:
            report['cases'][-1].update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['raw','opt'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',action='append')
    p.add_argument('--replay',action='store_true')
    args=p.parse_args()
    run(args.output,args.mode,args.case,args.replay)
