#!/usr/bin/env python3
"""Run the public Task examples with native console output and a real Return key."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_console_display import glyph
from test_dos_stack import execute, ownership
from test_heap_api import clean_ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
EXAMPLES = {
    'amiga-ports': (4, 2, ('Send: 10,20', 'Reply: 60,70',
                         'Message returned; resources released.')),
    'tasks': (8, 4, ('TASKS EXEC OK',)),
    'signals': (8, 7, ('SIGNALS OK',)),
}
PROMPT = 'Press RETURN to exit.'


def check_example(bridge, program, name):
    module = {'amiga-ports': 'AMIGAPORTS', 'tasks': 'TASKSEXEC', 'signals': 'SIGNALDEMO'}[name]
    image = dict(program['image'], data=[s for s in program['image']['data']
                                        if s['name'].startswith(f'M_{module}_')])
    def expect(symbol, expected, words=False):
        actual = data(bridge, image, symbol, words)
        require(actual == expected, f'{symbol}: {actual}, expected {expected}')
    expect('consoleFailed', [0])
    expect('console', [0, 0, 0])
    expect('consoleKey', [10])
    if name == 'amiga-ports':
        expect('completed', [1])
        expect('failureCode', [0])
        expect('sameMessage', [1])
        expect('receivedX', [60], True)
        expect('receivedY', [70], True)
        return
    elif name == 'tasks':
        from generate_tasks import ABI
        expect('checks', [ABI['version'], 128, 0, 1], True)
        expect('progress', [1, 1, 2])
        task_symbol, count = 'workers', 3
    else:
        expect('admitted', [6])
        expect('ready', [6])
        expect('finished', [6])
        return
    from generate_tasks import ABI
    tasks = data(bridge, image, task_symbol)
    for index in range(count):
        require(tasks[index*ABI['task']['size']+12] == 6, 'Worker did not retire')


def run(name, mode, out, from_build=None):
    capacity, created, lines = EXAMPLES[name]
    source = ROOT/'examples'/f'{name}.act'
    out.mkdir(parents=True, exist_ok=True)
    program = (read_build(from_build.resolve()) if from_build else
               build(compiler(ROOT/'build/actionc'), source, out/'program',
                     optimize=mode == 'opt', tasks=True, task_capacity=capacity, console=True))
    require(program['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
    require(program['build']['source_sha256'] == sha256(source), 'Example source changed')
    require(program['build']['console_enabled'], 'Native console required')
    if from_build:
        previous = json.loads((from_build.resolve().parent/'results.json').read_text())
        require(previous['build']['xex_sha256'] == program['build']['xex_sha256'],
                'Replay evidence belongs to another image')
        for path in (source, ROOT/'examples/example-output.inc'):
            require(previous['inputs'].get(str(path.relative_to(ROOT))) == sha256(path),
                    'Replay example or output helper changed')
    bridge_dir = ROOT/'build/shell-paced-bridge'
    rom = ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Wrong emulator')
    require(sha256(rom) == PIN['rom']['sha256'], 'Wrong ROM')
    report = dict(status='running', tier='development', example=name, mode=mode,
                  build=program['build'], pin=PIN,
                  inputs={str(p.relative_to(ROOT)): sha256(p) for p in
                          (source, ROOT/'examples/example-output.inc', Path(__file__))},
                  bank_zero_delta=dict(fixed=0, per_task=0),
                  capacity=capacity)
    try:
        with emulator(bridge_dir, rom, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, rom, PIN)
            saved = {}
            def before_run(b):
                saved.update(address=b.peek16(88), cursor=b.peek(752), mask=b.peek(16))
                saved['screen'] = b.memdump(saved['address'], 960)
                b._cmd_ok('KEY ALL up')
                # Pause at a native VBI once the complete prompt has been drawn.
                # Observe ordinary display state; the example needs no test gates.
                prompt_address = saved['address']+len(lines)*40
                condition = '&'.join(f'db(${prompt_address+i:x})={glyph(ord(c))}'
                                     for i, c in enumerate(PROMPT))
                cursor_address = saved['address']+(len(lines)+1)*40
                condition += f'&(db(${cursor_address:x})=128)'
                marker = program['labels']['native_nmi']
                b.bp_set(marker, condition=condition)
                run_to(b, marker, frame_limit=3000, timeout=90, condition=condition)
                screen = b.memdump(saved['address'], 960)
                expected = bytearray(960)
                for row, line in enumerate((*lines, PROMPT)):
                    expected[row*40:row*40+len(line)] = bytes(map(glyph, line.encode('ascii')))
                expected[(len(lines)+1)*40] = 128  # cursor at the next line
                (out/'output.screen.bin').write_bytes(screen)
                require(screen == expected, 'Native console output/cursor differs')
                report['output'] = list(lines)
                report['screen_sha256'] = sha256(out/'output.screen.bin')
                require(b._cmd_ok('KEY RETURN down')['raw_scan'], 'Physical Return required')
                capture = program['build']['memory']['console_storage']['CAPTURE']
                previous = b.eval_expr(f'dw(${capture+10:x})')
                b.bp_clear_all()
                condition = f'dw(${capture+10:x})>{previous}'
                b.bp_set(marker, condition=condition)
                run_to(b, marker, frame_limit=120, timeout=15, condition=condition)
                b._cmd_ok('KEY RETURN up')
                b.bp_clear_all()
            runtime, _ = execute(bridge, program, before_run=before_run,
                                 frame_limit=3000, timeout=90)
            report['runtime'] = runtime
            check_example(bridge, program, name)
            require(runtime['created'] == created, 'Wrong application/console Task count')
            require(runtime['os_calls'] == 0, 'Example still used the ROM output adapter')
            require(runtime['root_task'][16:20] == [255, 255, 0, 0], 'Root leaked a signal')
            require(bridge.memdump(saved['address'], 960) == saved['screen'] and
                    bridge.peek(16) == saved['mask'] and bridge.peek(752) == saved['cursor'],
                    'OS display/input restoration failed')
            if capacity == 8:
                ownership(bridge, program, program['output'])
            else:
                clean_ownership(bridge, program, program['output'])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Task example passed: {name} {mode}', flush=True)
    return report


def main(default_examples=tuple(EXAMPLES)):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', choices=tuple(EXAMPLES), action='append')
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path,
                        help='Replay a recorded build (one example; requires adjacent results.json)')
    args = parser.parse_args()
    examples = args.example or default_examples
    require(not args.from_build or len(examples) == 1, 'Replay requires one example')
    for name in examples:
        out = args.output.resolve() if len(examples) == 1 else args.output.resolve()/name
        run(name, args.mode, out, args.from_build)


if __name__ == '__main__':
    main()
