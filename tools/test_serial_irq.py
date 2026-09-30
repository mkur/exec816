#!/usr/bin/env python3
"""Qualify the shared native/emulation serial adapter and scoped ownership."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from os_boundary import ROOT, require, sha256
from sio_latency import build, execute

PIN = json.loads((ROOT/'toolchain/altirra-sio-irq.json').read_text())
SOURCE = ROOT/'probes/sio-irq/probe.s'
ADAPTER = ROOT/'platform/altirraos/serial-irq.inc'


def case(output, bridge_dir, rom, *, trace=True, initial_critic=0, **options):
    program = build(output, source=SOURCE, critical=1,
                    extra_defines={k.upper(): options.pop(k) for k in ('timer_irq', 'abort')
                                   if k in options}, **options)
    program['source_inputs'] = [ADAPTER]
    originals = {}

    def before(bridge, program):
        bridge.poke(0x42, initial_critic)
        originals['deferred'] = bridge.memdump(0x224, 2)
        originals['timer'] = bridge.memdump(0x210, 2)
        originals['mask'] = bridge.memdump(0x10, 1)[0]
        originals['skctl'] = bridge.memdump(0x232, 1)

    def after(bridge, program, result):
        labels = program['labels']
        word = lambda key: bridge.peek16(labels[key])
        byte = lambda key: bridge.memdump(labels[key], 1)[0]
        require(word('OWN_CHECKS') == 3, 'Busy/duplicate ownership checks failed')
        require(byte('SIO_ACTIVE') == 0, 'Serial ownership not released')
        require(bridge.memdump(0x224, 2) == originals['deferred'] and
                bridge.memdump(0x210, 2) == originals['timer'], 'Callback vectors not restored')
        require(bridge.memdump(0x232, 1) == originals['skctl'], 'SKCTL shadow not restored')
        require(bridge.memdump(0x10, 1)[0] == originals['mask'], 'Fixture mask not restored')
        require(word('DURING_DEFERRED') == 0, 'Stage-two VBI ran during serial ownership')
        if program['defines']['VBI']:
            require(word('POST_RELEASE_VBIS') >= 2, 'No VBI after release')
            require((word('DEFERRED_COUNT') > 0) == (initial_critic == 0),
                    'Release did not restore the previous VBI critical state')
        timer = program['defines'].get('TIMER_IRQ', 0)
        expected_mask = originals['mask'] ^ 0x80
        if timer:
            expected_mask |= 1
            require(word('TIMER_COUNT') > 0, 'Unowned timer IRQ was not serviced')
            require(word('CONCURRENT_IRQS') > 0, 'No simultaneous serial/timer source tested')
        require(byte('MASK_ON_RELEASE') == expected_mask,
                'Release lost another IRQ owner mask change')
        require(byte('MASK_ON_SECOND_RELEASE') == expected_mask, 'Repeated release changed ownership')
        result['ownership'] = dict(checks=word('OWN_CHECKS'), active=byte('SIO_ACTIVE'),
            initial_critic=initial_critic, deferred_during=word('DURING_DEFERRED'),
            deferred_after=word('DEFERRED_COUNT'), post_release_vbis=word('POST_RELEASE_VBIS'),
            timer_irqs=word('TIMER_COUNT'), concurrent_irqs=word('CONCURRENT_IRQS'),
            mask_on_release=byte('MASK_ON_RELEASE'),
            vectors='restored', skctl='restored')

    result = execute(program, bridge_dir, rom, trace, True, before, after)
    require(result['resolved_machine'] == PIN['machine'], 'Adapter machine profile mismatch')
    # An abort owns a finite partial stream, and does not promise its last byte
    # completes. Such cases run without the normal-stream timing oracle.
    result['adapter_pin_sha256'] = sha256(ROOT/'toolchain/altirra-sio-irq.json')
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-dir', type=Path, default=ROOT/'build/altirra-latency-bridge')
    parser.add_argument('--pinned-bridge-dir', type=Path, default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/sio-irq/qualification')
    parser.add_argument('--case', action='append')
    args = parser.parse_args()
    require(sha256(args.rom) == PIN['rom']['sha256'], 'Unpinned ROM')
    require(sha256(args.pinned_bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Unpinned replay emulator')
    # Observation changes are recorded separately from the execution pin.
    baseline = json.loads((ROOT/'docs/qualification/sio-latency.json').read_text())
    observers = {c['emulator_sha256'] for c in baseline['cases'] if c.get('instrumented')}
    require(sha256(args.bridge_dir/'AltirraBridgeServer') in observers, 'Unqualified observer build')
    cases = [('long', dict(count=65535)), ('idle', dict(count=16384, busy=0)),
             *[(f'phase_{p}', dict(phase=p)) for p in (3, 7, 13)],
             ('old_critic', dict(initial_critic=0x42)),
             ('timer_coexistence', dict(timer_irq=1)),
             ('negative_stall', dict(vbi=0, stall=1600, count=256)),
             ('abort', dict(abort=1, count=64, trace=False)),
             ('pinned_replay', dict(count=65535, trace=False))]
    if args.case:
        require(set(args.case) <= {name for name, _ in cases}, 'Unknown case')
        cases = [(name, options) for name, options in cases if name in args.case]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                  platform=PIN, scope='Serial IRQ adapter and scoped ownership; no public signals',
                  cases=[], status='running')
    try:
        for name, options in cases:
            binary = args.pinned_bridge_dir if options.get('trace') is False else args.bridge_dir
            result = case(output/name, binary.resolve(), args.rom.resolve(), **options)
            report['cases'].append(dict(name=name, **result))
            if 'trace' in result:
                timing = result['trace']
                print(f"{name}: {timing['verdict']}; max {timing['ready_to_refill']['max_us']:.3f} us; "
                      f"{timing['deadline_misses']} misses", flush=True)
                if name == 'negative_stall':
                    require(timing['verdict'] == 'fail', 'Negative control did not detect late refills')
                elif name != 'timer_coexistence':
                    require(timing['verdict'] == 'pass', 'Adapter misses its qualified deadline: '+name)
            else:
                print(name+': ownership/context checks pass', flush=True)
        named = {c['name']: c for c in report['cases']}
        if 'long' in named and 'pinned_replay' in named:
            for key in ('xex_sha256', 'sent', 'posts', 'waits', 'vbis', 'clock_before',
                        'clock_after', 'background_progress', 'worker_saved_s',
                        'background_saved_s', 'ownership'):
                require(named['long'][key] == named['pinned_replay'][key],
                        'Observer changed execution: '+key)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
