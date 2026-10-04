#!/usr/bin/env python3
"""Emitted bounded batches against an independent linear terminal per prefix."""
import argparse
import json
import struct
from pathlib import Path

from bitmap_console_oracle import Terminal
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from stack_budget import stack_usage

SOURCE, CELLS, RESULTS = 0xa0000, 0xbfff8, 0xd0000


def corpus():
    return [
        (80, 30, 0, b'one\ntwo\nthree\nfour\n', 0),
        (80, 30, 70, b'partial first row and wrap\nlast partial', 0),
        (80, 30, 0, b'x' * 64, 0),
        (80, 30, 0, b'x' * 65, 0),
        (80, 30, 0, b'x' * 513, 0),
        (80, 30, 0, b'\n' * 95, 0),
        (5, 3, 3, b'abc\n' * 12, 0),
        (1, 3, 0, b'ab\n' * 8, 0),
        (17, 3, 2, b'AB\tC\rD\bE\x7fF\x80\nZ\x0cafter\n', 0),
        (80, 1, 0, b'A\nB' * 7, 0),
        (1, 1, 0, b'ABC\n', 0),
        (80, 30, 0, b'one\ntwo\nthree\n', 1),
        (40, 24, 30, b'append\n' * 10 + b'final', 0),
    ]


def payload(cases):
    return struct.pack('<H', len(cases)) + b''.join(
        struct.pack('<5H', w, h, col, len(text), wrap) + text
        for w, h, col, text, wrap in cases)


def digest(cells):
    total = weighted = 0
    for byte in cells:
        total = (total + byte) & 65535
        weighted = (weighted + total) & 65535
    return total | weighted << 16


def oracle(raw, cases):
    current = None
    previous = 0
    totals = dict(prefixes=0, batches=0, multirow_batches=0, tick_flushes=0,
                  limit_flushes=0, control_flushes=0, logical_scrolls=0)
    for offset in range(0, len(raw), 160):
        words = struct.unpack('<80H', raw[offset:offset+160])
        case, stage, position, used, row, col, origin, phase, reason, rows, size, turns, operation, dirty, age = words[:15]
        w, h, column, text, wrap = cases[case]
        if current != case:
            require(case == (0 if current is None else current+1), 'Skipped corpus case')
            if current is not None:
                require(previous == len(cases[current][3]), 'Incomplete preceding case')
            current, previous, scrolls = case, 0, 0
            terminal = Terminal(w, h)
            terminal.cells[:] = bytes(33 + i % 90 for i in range(w*h))
            terminal.row, terminal.column = h-1, column
            screen = bytearray(terminal.cells)
        require(0 <= previous <= position <= len(text), 'Invalid accepted prefix')
        if stage != 2:
            require(position-previous == used and used <= 64, 'Source quantum changed')
            before = scrolls
            for byte in text[previous:position]:
                if terminal.row == h-1 and (byte == 10 or byte == 9 and (terminal.column//8+1)*8 >= w
                    or byte >= 32 and byte != 127 and terminal.column == w-1):
                    scrolls += 1
                terminal.feed(bytes([byte]))
                if byte == 12:
                    scrolls = 0
            if stage == 1:
                require(scrolls-before <= 1, 'More than one recycled row per turn')
            previous = position
            totals['prefixes'] += 1
        require((row, col) == (terminal.row, terminal.column), 'Cursor differs from linear terminal')
        require(origin == (scrolls % h)*w and operation == 0, 'Circular origin/edit differs')
        require(words[17] | words[18] << 16 == digest(terminal.cells), 'Accepted prefix cells differ')
        require(words[19] == 44, 'Batch layout differs')
        if stage == 1:
            require(phase == 1 and dirty == 0 and rows <= min(4, h-1)
                    and size <= 256 and turns <= 4, 'Batch limits/damage differ')
        if stage == 2:
            require(phase == 2 and position == previous, 'Publication changed accepted prefix')
            if rows:
                screen[:] = screen[rows*w:] + b' '*(rows*w)
            spans = [(words[20+y*2], words[21+y*2]) for y in range(h)]
            require(dirty == sum(first < last for first, last in spans), 'Dirty summary differs')
            for y, (first, last) in enumerate(spans):
                require(0 <= first <= w and 0 <= last <= w, 'Invalid dirty span')
                if first < last:
                    screen[y*w+first:y*w+last] = terminal.cells[y*w+first:y*w+last]
            require(screen == terminal.cells, 'Copy/fill plus final damage loses accepted text')
            totals['batches'] += 1
            totals['multirow_batches'] += rows > 1
            totals['logical_scrolls'] += rows
            for value, name in ((1, 'limit_flushes'), (2, 'tick_flushes'), (4, 'control_flushes')):
                totals[name] += reason == value
        elif stage == 3:
            screen[:] = terminal.cells
        require(stage in (1, 2, 3), 'Unknown observation')
    require(current == len(cases)-1 and previous == len(cases[-1][3]), 'Incomplete corpus')
    require(all(totals[k] for k in ('multirow_batches', 'tick_flushes', 'limit_flushes', 'control_flushes')),
            'Missing batch boundary coverage')
    return totals


def run(out, mode, replay=False):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases = corpus()
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    bridge, rom = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
    result = dict(status='running', tier='development', mode=mode)
    try:
        require(sha256(bridge/'AltirraBridgeServer') == pin['emulator']['sha256'], 'Unpinned emulator')
        p = read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/console_batch_core.act', out/'program',
                  optimize=mode == 'opt', tasks=True, task_capacity=8, console_test=True,
                  image_data=[(SOURCE, payload(cases)), (CELLS-16, bytes([0xa5])*2432),
                              (RESULTS, bytes([0xa5])*128032)])
        require(p['build']['optimize'] == (mode == 'opt')
                and p['build']['xex_sha256'] == sha256(p['xex']), 'Changed replay image')
        result.update(build=p['build'], pin=pin)
        with emulator(bridge, rom, out, pin=pin) as b:
            result['machine'] = verify_machine(b, rom, pin)
            try:
                runtime, _ = execute(b, p, timeout=180, frame_limit=12000)
            except Exception:
                print('Batch core state', {name: data(b, p['image'], name, True)
                      for name in ('checks', 'samples', 'caseIndex', 'position', 'length', 'used')},
                      'PC24', hex(b.eval_expr('@xpc')), flush=True)
                raise
            ownership(b, p, p['output'])
            count = data(b, p['image'], 'samples', True)[0]
            require(count < 800, 'Observation capacity exceeded')
            raw = b.memdump(RESULTS, count*160)
            (out/'prefixes.bin').write_bytes(raw)
            result['coverage'] = oracle(raw, cases)
            require(b.memdump(CELLS-16, 16) == bytes([0xa5])*16
                    and b.memdump(CELLS+2400, 16) == bytes([0xa5])*16, 'Cell guard changed')
            require(b.memdump(RESULTS+count*160, 32) == bytes([0xa5])*32, 'Output extent changed')
            result.update(runtime=runtime, checks=data(b, p['image'], 'checks', True)[0],
                          stack_usage=stack_usage(b, p['build']['memory']))
        result.update(status='pass', batch_bytes=44,
                      bank_zero_delta=dict(fixed=0, root_kernel=0, per_task=[0]*8, private_idle=0))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Console batch core passed', mode, result['coverage'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output, args.mode, args.replay)
