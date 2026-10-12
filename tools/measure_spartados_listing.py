#!/usr/bin/env python3
"""Current packaged DIR/LIST timings, including command loading and output.

Guest-memory edits invalidate clean read caches and prefill unmeasured cooked
line input at an idle prompt. Return is a physical key. All timing markers
observe existing instructions, without guest counters.
"""
import argparse
import json
import shutil
import statistics
from pathlib import Path
from types import SimpleNamespace

import adapter_state as adapter
from bitmap_console_performance import native_markers
from native_program import ROOT, read_build, require, sha256
from measure_read_8k import observe
from measure_loading_breakdown import packets
from sector_images import ATRImage
from sio_transaction_trace import BASE_HZ, read_events
from trace_command_io import stats
import test_demo


# Private packed native records, not public ABI. Fail rather than edit unknown
# layouts. Record alignment is two; far pointers have alignment one.
LAYOUT_INPUTS = {
    'lib/io/blocktypes.act': 'e8989c86bac3c8af9342e63788a62d7c7a623c2973a84dd82ccf7d9dcec38da1',
    'lib/fs/fsbtypes.act': '1157a499f23b7fc73379b02286316c176dfbbe12096db1b2bae278bd81388f66',
    'lib/spartados/sdfstypes.act': 'dbfdcdac81b271a7b3f5d164dae7262bf1491e32c8f7e2ea91c26a1d283c9391',
}


def directory_rows(path, directory):
    """Read stored directory order and sizes independently of guest metadata."""
    image = ATRImage(path.read_bytes())
    word = lambda data, at: int.from_bytes(data[at:at+2], 'little')

    def contents(start):
        pages, sectors = [], []
        while start:
            require(start not in pages, 'Cyclic directory map')
            pages.append(start)
            page = image.sector(start)
            sectors.extend(word(page, i) for i in range(4, len(page), 2))
            start = word(page, 0)
        raw = b''.join(image.sector(s) for s in sectors if s)
        length = int.from_bytes(raw[3:6], 'little')
        require(length <= len(raw) and length % 23 == 0, 'Bad directory length')
        rows = []
        for pos in range(23, length, 23):
            row = raw[pos:pos+23]
            if not row[0]:
                break
            if row[0] & 16:
                continue
            require(row[0] & 0xc8 == 8, 'Invalid directory entry')
            name = row[6:14].rstrip(b' ')
            ext = row[14:17].rstrip(b' ')
            if ext:
                name += b'.' + ext
            rows.append(dict(name=name.decode('ascii'), directory=bool(row[0] & 32),
                             bytes=int.from_bytes(row[3:6], 'little'), start=word(row, 1)))
        return rows

    rows = contents(word(image.sector(1), 9))
    for part in directory.split('/'):
        if part:
            item = next(r for r in rows if r['name'] == part.upper())
            require(item['directory'], 'Listing path is not a directory')
            rows = contents(item['start'])
    return rows


def instruction_pc(program, begin, end, needle):
    """Locate a checked instruction in the final assembled native image."""
    lo, hi = program['labels'][begin], program['labels'][end]
    raw = bytearray(hi-lo)
    if hi < 65536:
        base = adapter.resident_addresses(program['build']['memory']['profile'])['RESIDENT_BASE']
        raw[:] = (program['output']/'hosted.bin').read_bytes()[lo-base:hi-base]
    else:
        for segment in program['image']['segments']:
            start = max(lo, segment['address'])
            end_address = min(hi, segment['address']+len(segment['bytes']))
            if start < end_address:
                raw[start-lo:end_address-lo] = bytes(segment['bytes'][start-segment['address']:end_address-segment['address']])
    hits = [lo+i for i in range(len(raw)-len(needle)+1) if raw[i:i+len(needle)] == needle]
    require(len(hits) == 1, 'Missing/ambiguous instruction marker: ' + begin)
    return hits[0]


def markers(program):
    names = [
        ('SHELLAPP_SHELLONECOMMAND', 'command'), ('SHELLAPP_SHELLDISPATCH', 'dispatch'),
        ('SHELLAPP_SHELLDIR', 'dir'), ('SHELLAPP_SHELLEXTERNAL', 'external'),
        ('PROGRAMFILE_LOAD', 'load'), ('PROCESS_START', 'process_start'),
        ('PROCESS_WAIT', 'process_wait'), ('DOSCALLS_WRITE', 'write'),
        ('DOSCLIENT_CALL', 'dos_call'), ('BLOCKCACHE_READ', 'cache_read'),
        ('SDFS_CACHE', 'map_cache'), ('SDFS_VALIDATEMAP', 'validate_map'),
        ('SDFSFILE_MEASURE', 'file_measure'), ('SDFSDIR_MEASURE', 'directory_measure'),
        ('SDFSEXTENTS_LOOKUP', 'extent_lookup'), ('FSINFO_CLEAR', 'fib_clear'),
        ('DOSCALLS_LOCK', 'lock'), ('DOSCALLS_INFORMATION', 'metadata'),
        ('CONSOLEBITMAP_TEXT', 'bitmap_text'),
        ('CONSOLEBITMAP_TEXTCARET', 'bitmap_text_caret'),
        ('CONSOLEBITMAP_CLIPPEDTEXT', 'bitmap_clipped_text'),
    ]
    routines = native_markers(program, names)
    require(all(k in routines and routines[k]['returns'] for k in ('command', 'write', 'load', 'metadata')), 'Missing listing markers')
    points = {}
    for name, routine in routines.items():
        points[name+'_entry'] = routine['entry']
        for i, pc in enumerate(routine['returns']):
            points[name+'_return_'+str(i)] = pc
    points['gateway'] = instruction_pc(program, 'native_cop', 'dispatch_call',
                                      b'\xee'+adapter.GATE_COUNT.to_bytes(2, 'little'))
    if 'ideplus_write_register' in program['labels']:
        # At this store X is the register and A8 is the value being written.
        points['ata_command'] = instruction_pc(program, 'ideplus_write_register',
                                              'ideplus_write_register_end', b'\x9f\x00\xd1\x00')
    return dict(routines=routines, marks=points)


def invalidate(context):
    """Mirror BLOCKIO/SDFS invalidation, with no running filesystem operation."""
    c = context
    registry = c.p['build']['memory']['dos_storage']['SHARED']
    service = c.number(registry+68, 3)
    block = c.number(service, 3)
    work = c.number(service+3, 3)
    state = c.number(work+170, 3)
    require(service and block and work and state, 'Missing filesystem state')
    require(c.number(block+24, 1) == 0, 'Filesystem block request still active')
    cache = block+30
    tags, blocks = c.number(cache, 3), c.number(cache+12, 2)
    require(tags and blocks == 512, 'Expected the current 64 KiB read cache')
    old = bytearray(c.b.memdump(tags, blocks*12))
    for at in range(0, len(old), 12):
        old[at:at+3] = bytes(3)
    c.b.memload(tags, old)
    c.b.memload(block+9, bytes(3))       # Adapter.cached
    c.b.memload(block+20, bytes(2))      # Adapter.valid
    c.b.memload(state, bytes(3))        # BackendState.cached
    c.b.memload(state+10, bytes(5))     # allocated, firstEmpty, valid
    c.b.memload(state+718, bytes(3))    # directoryVolume
    extents = c.number(state+726, 3)
    if extents:
        c.b.memload(extents, bytes(3))
        c.b.memload(extents+8, bytes(3))  # filled, next, pending
    cleared = c.b.memdump(tags, blocks*12)
    require(all(cleared[i:i+3] == bytes(3) for i in range(0, len(cleared), 12)), 'Cold cache still has tags')
    return dict(cache=cache, blocks=blocks, backend_state=state, extent_cache=extents)


def prefill(c, text):
    """Prepare the idle line editor; its ordinary Return/Drain executes it."""
    handle = c.number(c.saved['shell'], 3)
    session = c.number(handle+16, 3)
    require(session and c.number(session, 2) and c.number(session+400, 1) == 1,
            'Expected a live cooked reader')
    require(c.number(session+2, 2) == c.number(session+4, 2) == c.number(session+10, 1) ==
            c.number(session+11, 1) == c.number(session+12, 1) == 0, 'Input session is not empty')
    raw = text.encode('ascii')
    require(len(raw) < 256, 'Benchmark command exceeds cooked line capacity')
    c.b.memload(session+16, raw)
    c.b.memload(session+2, len(raw).to_bytes(2, 'little'))
    c.b.memload(session+402, len(raw).to_bytes(2, 'little'))


def submit(c, text, physical=False):
    if physical:
        return c.command(text)
    print('Benchmark command:', text, flush=True)
    previous = c.number(c.saved['scope']+14)
    prefill(c, text)
    c.press('\n')
    c.ready(previous)
    c.result()
    return c.cells(text)


def exercise(c, media, repeats, selected, physical):
    manifest = c.manifest
    require(manifest['bitmap'] and manifest['shell_only'], 'Use a standalone VBXE shell demo')
    c.saved['measurements'] = []
    ledger = c.ledger()
    for verb, directory, nil in selected:
        rows = directory_rows(media, directory)
        expected = b''.join((r['name'] + ('/' if r['directory'] else ' '+str(r['bytes']))).encode().ljust(80, b' ')
                            for r in rows)+b'> '
        text = verb + (' SYS:'+directory if directory else '') + (' >NIL:' if nil else '')
        for sample in range(repeats+1):
            submit(c, 'CLS', physical)
            if sample == 0:
                layout = invalidate(c)
            cache = layout['cache']
            before = dict(hits=c.number(cache+16), misses=c.number(cache+20))
            start = c.b.eval_expr('@clk')
            screen = submit(c, text, physical)
            if not nil:
                require(expected in screen, 'Listing differs from media: '+text)
            require(c.ledger() == ledger, 'Listing retained owned resources')
            c.saved['measurements'].append(dict(command=text, temperature='cold' if sample == 0 else 'warm',
                sample=sample, rows=rows, input_clock=start, settled_clock=c.saved['settled_clock'],
                cache_before=before, cache_after=dict(hits=c.number(cache+16), misses=c.number(cache+20)),
                cold_layout=layout if sample == 0 else None))
    c.save_screen(c.p['output']/'boot-smoke.png')
    if physical:
        for character in 'EXIT':
            c.press(character)
    else:
        prefill(c, 'EXIT')
    c.b._cmd_ok('KEY RETURN down')
    c.b.bp_clear_all()


def spans(events, routines):
    entries, returns, active, result = {}, {}, {}, []
    for name, routine in routines.items():
        entries.setdefault(routine['entry'], []).append(name)
        for pc in routine['returns']:
            returns.setdefault(pc, []).append(name)
    for tick, e in events:
        if e[0] != 'cpu':
            continue
        pc, dp = int(e[4], 16), int(e[9], 16)
        for name in returns.get(pc, []):
            key = name, dp
            if key in active:
                begin = active.pop(key)
                result.append(dict(kind=name, dp=dp, begin=begin, end=tick, ms=(tick-begin)/BASE_HZ*1000))
        for name in entries.get(pc, []):
            if not routines[name]['returns']:
                # Imported APIs may be a JML alias with no RTL of their own.
                # Count the entry; do not invent a return or elapsed duration.
                result.append(dict(kind=name, dp=dp, begin=tick, end=tick,
                                   ms=0, entry_only=True))
                continue
            key = name, dp
            require(key not in active, 'Nested listing observation: '+name)
            active[key] = tick
    require(not active, 'Unfinished listing routine observations')
    return result


def analyze(bundle, record, definition):
    events = read_events(bundle/'emulator.log')
    wire = packets(events)
    measured = spans(events, definition['routines'])
    windows = [r for r in measured if r['kind'] == 'command']
    result = []
    for m in record['measurements']:
        candidates = [w for w in windows if in_clock_window(w, m['input_clock'], m['settled_clock'])]
        require(len(candidates) == 1, 'Incomplete command observation: '+m['command'])
        w = candidates[0]
        inside = [r for r in measured if w['begin'] <= r['begin'] <= r['end'] <= w['end'] and r['kind'] != 'command']
        cpus = [(t,e) for t,e in events if w['begin'] <= t <= w['end'] and e[0] == 'cpu']
        writes = sorted((r for r in inside if r['kind'] == 'write'), key=lambda r:r['begin'])
        is_dir, nil = m['command'].startswith('DIR'), '>NIL:' in m['command']
        expected_writes = len(m['rows']) if is_dir else sum(3 if r['directory'] else 4 for r in m['rows'])
        require(len(writes) == expected_writes, 'Unexpected listing Write count')
        first_count = 1 if is_dir else (3 if m['rows'][0]['directory'] else 4)
        # DIR uses one Write per row; LIST uses three/four. The next row's
        # first Write bounds the first row's drawing, including its newline
        # and caret. This works for imported JML aliases without RTL markers.
        first_limit = writes[first_count-1]['end'] if not writes[first_count-1].get('entry_only') else (
            writes[first_count]['begin'] if first_count < len(writes) else w['end'])
        drawings = [r for r in inside if r['kind'].startswith('bitmap_') and writes[0]['begin'] <= r['begin'] <= r['end'] <= first_limit]
        require(nil or drawings, 'First row has no completed bitmap draw')
        sio_packets = [p for p in wire if w['begin'] <= p['begin'] <= w['end']]
        for packet in sio_packets:
            require(len(packet['tx']) == 5 and [v for _,v,_ in packet['tx'][:2]] == [49, 82],
                    'Listing issued a non-read SIO command')
        sio = len(sio_packets)
        ata = [int(e[5], 16)&255 for t,e in cpus if int(e[4], 16) == definition['marks'].get('ata_command') and int(e[6], 16) == 23]
        require(all(v == 32 for v in ata), 'Listing wrote/flushed IDE media')
        item = dict(command=m['command'], temperature=m['temperature'], sample=m['sample'], rows=len(m['rows']),
            total_ms=w['ms'], first_write_ms=(writes[0]['begin']-w['begin'])/BASE_HZ*1000,
            first_row_write_complete_ms=(first_limit-w['begin'])/BASE_HZ*1000 if not writes[first_count-1].get('entry_only') else None,
            first_row_bitmap_complete_ms=(max(r['end'] for r in drawings)-w['begin'])/BASE_HZ*1000 if drawings else None,
            output_writes=len(writes), physical_sio_commands=sio, ata_reads=len(ata), ata_writes=0,
            kernel_calls=sum(int(e[4], 16) == definition['marks']['gateway'] for _,e in cpus),
            cache_hits=m['cache_after']['hits']-m['cache_before']['hits'],
            cache_misses=m['cache_after']['misses']-m['cache_before']['misses'],
            sio_read_sectors=[p['tx'][2][1]+256*p['tx'][3][1] for p in sio_packets],
            sio_read_payload_bytes=sum(len(p['rx'])-3 for p in sio_packets),
            routines={name:stats([r['ms'] for r in inside if r['kind'] == name]) for name in definition['routines'] if name != 'command'})
        for name, routine in definition['routines'].items():
            if name != 'command' and not routine['returns']:
                item['routines'][name].update(entry_only=True, mean_ms=None,
                    min_ms=None, max_ms=None, sum_ms=None)
        for name in ('load', 'write', 'metadata'):
            intervals = [r for r in inside if r['kind'] == name]
            item[name+'_kernel_calls'] = sum(
                int(e[4], 16) == definition['marks']['gateway'] and
                any(r['begin'] <= t <= r['end'] for r in intervals)
                for t,e in cpus)
        for kind in ('file_measure', 'directory_measure', 'extent_lookup'):
            require(item['routines'][kind]['count'] == 0, 'Ordinary listing measured selected extents')
        require(item['routines']['metadata']['count'] == len(m['rows'])+2, 'Incorrect enumeration count')
        if m['temperature'] == 'warm':
            require(sio == len(ata) == item['cache_misses'] == 0, 'Warm listing did physical I/O')
        result.append(item)
    return result


def in_clock_window(window, start, end):
    """Align bridge @clk to the observer's unwrapped 32-bit clock epoch."""
    period = 1 << 32
    offset = round((window['begin']-start)/period)*period
    start, end = start+offset, end+offset
    if end < start:
        end += period
    return start <= window['begin'] <= window['end'] <= end


def run(bundle, output, repeats=3, media=None, commands=None, physical=False):
    require(repeats >= 1, 'Need a warm repetition')
    for path, digest in LAYOUT_INPUTS.items():
        require(sha256(ROOT/path) == digest, 'Update private cache layout for '+path)
    output.mkdir(parents=True, exist_ok=True)
    copied = output/'bundle'
    require(not copied.exists(), 'Choose a fresh measurement output')
    shutil.copytree(bundle, copied, symlinks=True, ignore=shutil.ignore_patterns('emulator.log', 'pixels-*'))
    program = read_build(copied)
    require(program['build']['optimize'], 'Measure optimized guest code')
    definition = markers(program)
    (output/'markers.json').write_text(json.dumps(definition, indent=2)+'\n')
    observe(definition['marks'])
    # IDE's system.atr is the independently audited partition source, not SIO.
    media = media or copied/'system.atr'
    selected = commands or [(verb, path, nil) for verb in ('DIR', 'LIST') for path in ('', 'C') for nil in (False, True)]
    integration = SimpleNamespace(exercise=lambda c:exercise(c, media, repeats, selected, physical))
    manifest = json.loads((copied/'demo-manifest.json').read_text())
    override = media if not manifest.get('ide_only') and media != copied/'system.atr' else None
    record = test_demo.run(copied, boot_smoke=True, measurement_commands=[], profile_commands=True,
                           integration=integration, media_path=override,
                           measurement_media_sha256=sha256(override) if override else None)
    record['scope'] = 'Optimized standalone VBXE shell: DIR/LIST, cold cache invalidation, warm repeats, media-derived rows, physical pixels and EXIT cleanup'
    record['benchmark_input'] = 'Physical typing' if physical else 'Prefilled empty cooked-line buffer, physical Return, ordinary cooked Drain and shell dispatch; typing excluded from timing'
    (output/'run.json').write_text(json.dumps(record, indent=2)+'\n')
    return save_results(output, media)


def save_results(output, media=None):
    copied = output/'bundle'
    program = read_build(copied)
    manifest = json.loads((copied/'demo-manifest.json').read_text())
    record = json.loads((output/'run.json').read_text())
    definition = json.loads((output/'markers.json').read_text())
    require(definition == markers(program), 'Marker definitions differ from observed image')
    require(record['xex_sha256'] == sha256(copied/'program.xex') and
            record['bundle_manifest_sha256'] == sha256(copied/'demo-manifest.json'), 'Stale listing run')
    media = media or copied/'system.atr'
    expected = record['media_sha256'] if record['measurement_media_override'] else manifest['artifacts']['system.atr']
    require(sha256(media) == expected, 'Changed measurement directory media')
    rows = analyze(copied, record, definition)
    result = dict(status='pass', tier='development', transport='IDE' if manifest.get('ide_only') else 'SIO',
        scope='ShellOneCommand entry to final RTL; includes parsing, redirection, LIST load/launch/wait/cleanup; excludes typing and prompt. DOSCALLS implementations cover resident and loaded callers. Routine spans include preemption and overlap. First-row bitmap completion is the last synchronous text return before the row-ending Write returns, including newline/caret painting; this bounds fenced VRAM visibility, not monitor scanout.',
        cache_scope='Cold: all read-cache tags, scratch sector and SDFS map/directory/extent identities invalidated at idle prompt; mounts and current-directory lock remain admitted. Warm: exact command repeated after CLS; no filesystem changes.',
        compiler_revision=program['build']['revision'], compiler_sha256=program['build']['binary_sha256'],
        layout_inputs=LAYOUT_INPUTS, observer_sha256=sha256(Path(__file__)),
        xex_sha256=sha256(copied/'program.xex'), manifest_sha256=sha256(copied/'demo-manifest.json'),
        system_atr_sha256=sha256(media), log_sha256=sha256(copied/'emulator.log'),
        source_inputs=manifest['source_inputs'], sector_bytes=manifest['sector_bytes'],
        rom=record['rom'], machine=record['machine'], input=record['benchmark_input'],
        rows=rows, bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    for command in dict.fromkeys(r['command'] for r in rows):
        samples = [r for r in rows if r['command'] == command]
        warm = [r['total_ms'] for r in samples if r['temperature'] == 'warm']
        print(command, 'cold', round(samples[0]['total_ms'], 2), 'ms; warm median', round(statistics.median(warm), 2), 'ms', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--media', type=Path, help='Explicit SIO comparison media; hash recorded')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--command', choices=('DIR', 'LIST'), action='append')
    parser.add_argument('--analyze', action='store_true', help='Reanalyze retained run and trace without executing')
    parser.add_argument('--physical-input', action='store_true', help='Type every character physically instead of prefilling unmeasured cooked input')
    args = parser.parse_args()
    selected = [(verb, path, nil) for verb in args.command for path in ('', 'C') for nil in (False, True)] if args.command else None
    if args.analyze:
        save_results(args.output.resolve(), args.media.resolve() if args.media else None)
    else:
        run(args.bundle.resolve(), args.output.resolve(), args.repeats, args.media.resolve() if args.media else None, selected, args.physical_input)


if __name__ == '__main__':
    main()
