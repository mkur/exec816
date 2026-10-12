#!/usr/bin/env python3
"""Partition current LIST loading using passive markers in the packaged image.

Reuse the SpartaDOS listing fixture, optimized emission and independent output,
ownership, pixel and OS-restoration checks. No guest instructions are added.
"""
import argparse
import json
import os
import shutil
import statistics
from pathlib import Path
from types import SimpleNamespace

import measure_spartados_listing as listing
from bitmap_console_performance import native_markers
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events


PARENTS = ('programfile_load', 'program_load', 'o65_validate', 'o65_descriptor',
           'programproviders_resolve', 'programplace_allocate', 'o65wire_header')
ROUTINES = ('o65_validate', 'o65_descriptor', 'o65wire_header', 'o65wire_exports',
            'o65profile_imports', 'o65relocations_walk', 'program_load',
            'programproviders_resolve', 'programplace_allocate', 'programplace_copy',
            'programplace_patches', 'o65_release', 'o65read_u32', 'o65read_u16',
            'o65read_u8', 'o65read_take', 'o65read_name', 'o65read_string',
            'o65read_literal', 'o65read_equal')
ENV = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')


def markers(program):
    definition = listing.markers(program)
    extra = native_markers(program, [(name.upper(), name) for name in ROUTINES])
    require(len(extra) == len(ROUTINES), 'Missing current loader routine')
    definition['routines'].update(extra)
    image = program['image']
    names = {r['address']: r['name'][2:].rsplit('_', 1)[0].lower() for r in image['routines']}
    imported = {r['address'] for r in image['imports']}
    for name, address in program['labels'].items():
        if address in imported and not name.endswith('_end'):
            names.setdefault(address, name)
    decoder_path = ROOT/'build/actionc/tools/disassemble65816.py'
    decoder = {'__name__': 'list_loading_decoder'}
    exec(compile(decoder_path.read_text(), str(decoder_path), 'exec'), decoder)
    sites = {}
    for routine in image['routines']:
        caller = names[routine['address']]
        if caller not in PARENTS:
            continue
        segments = []
        for segment in image['segments']:
            lo = max(segment['address'], routine['address'])
            hi = min(segment['address']+len(segment['bytes']), routine['address']+routine['size'])
            if lo < hi:
                segments.append(dict(address=lo, executable=True,
                    bytes=segment['bytes'][lo-segment['address']:hi-segment['address']]))
        assembly = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
        for line in assembly.splitlines():
            instruction = line.split('  ', 1)[1][12:]
            if not instruction.startswith('JSL $'):
                continue
            pc = int(line.split('  ', 1)[0], 16)
            target = int(instruction[5:], 16)
            require(target in names, 'Unknown loader callee: '+instruction)
            key = f'call_{caller}_{pc:x}'
            sites[key] = dict(caller=caller, callee=names[target])
            definition['routines'][key] = dict(entry=pc, returns=[pc+4])
    require(set(site['caller'] for site in sites.values()) == set(PARENTS), 'Missing loader call sites')
    for name, routine in definition['routines'].items():
        definition['marks'][name+'_entry'] = routine['entry']
        for index, pc in enumerate(routine['returns']):
            definition['marks'][name+'_return_'+str(index)] = pc
    definition.update(sites=sites, decoder_sha256=sha256(decoder_path))
    return definition


def partition(parent, measured, sites, caller):
    """Direct callee spans plus caller instructions; nested totals stay separate."""
    selected = sorted((r for r in measured if r['kind'] in sites and
        sites[r['kind']]['caller'] == caller and r['dp'] == parent['dp'] and
        parent['begin'] <= r['begin'] <= r['end'] <= parent['end']), key=lambda r:r['begin'])
    previous, occupied = parent['begin'], 0
    ticks, counts = {}, {}
    for row in selected:
        require(row['begin'] >= previous, 'Overlapping direct loader calls')
        key = sites[row['kind']]['callee']
        duration = row['end']-row['begin']
        ticks[key] = ticks.get(key, 0)+duration
        counts[key] = counts.get(key, 0)+1
        occupied += duration
        previous = row['end']
    total = parent['end']-parent['begin']
    require(occupied <= total, 'Negative loader caller remainder')
    ticks['caller_instructions'] = total-occupied
    return dict(total_ms=total/BASE_HZ*1000,
                parts_ms={key:value/BASE_HZ*1000 for key,value in ticks.items()}, counts=counts)


def analyze(output, media=None):
    bundle = output/'bundle'
    program = read_build(bundle)
    definition = json.loads((output/'markers.json').read_text())
    require(definition == markers(program), 'Changed loader observation markers')
    record = json.loads((output/'run.json').read_text())
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    require(record['xex_sha256'] == sha256(bundle/'program.xex') and
            record['bundle_manifest_sha256'] == sha256(bundle/'demo-manifest.json'), 'Changed loader image')
    media = media or bundle/'system.atr'
    expected = record['media_sha256'] if record['measurement_media_override'] else manifest['artifacts']['system.atr']
    require(sha256(media) == expected, 'Changed listing media')
    ordinary = listing.analyze(bundle, record, definition)
    events = read_events(bundle/'emulator.log')
    measured = listing.spans(events, definition['routines'])
    commands = [r for r in measured if r['kind'] == 'command']
    result = []
    for sample, normal in zip(record['measurements'], ordinary):
        windows = [r for r in commands if listing.in_clock_window(r, sample['input_clock'], sample['settled_clock'])]
        require(len(windows) == 1, 'Missing LIST window')
        window = windows[0]
        inside = [r for r in measured if window['begin'] <= r['begin'] <= r['end'] <= window['end']]
        attempts = sorted((r for r in inside if r['kind'] == 'load'), key=lambda r:r['begin'])
        programs = [r for r in inside if r['kind'] == 'program_load']
        require(len(attempts) == 2 and len(programs) == 1, 'Changed LIST search/load path')
        row = dict(command=normal['command'], temperature=normal['temperature'], sample=normal['sample'],
                   command_ms=normal['total_ms'], load_ms=sum(r['ms'] for r in attempts),
                   load_kernel_calls=normal['load_kernel_calls'], cache_misses=normal['cache_misses'],
                   physical_sio_commands=normal['physical_sio_commands'], ata_reads=normal['ata_reads'],
                   attempts=[partition(r, inside, definition['sites'], 'programfile_load') for r in attempts],
                   partitions={}, nested={})
        for name in PARENTS:
            if name == 'programfile_load':
                continue
            parents = [r for r in inside if r['kind'] == name]
            require(len(parents) == 1, 'Expected one completed loader phase: '+name)
            row['partitions'][name] = partition(parents[0], inside, definition['sites'], name)
        successful = attempts[-1]
        for name in ROUTINES:
            calls = [r for r in inside if r['kind'] == name and
                     successful['begin'] <= r['begin'] <= r['end'] <= successful['end']]
            row['nested'][name] = dict(count=len(calls), inclusive_ms=sum(r['ms'] for r in calls))
        require(row['partitions']['program_load']['counts'].get('programplace_patches') == 2,
                'Missing preflight/application relocation passes')
        result.append(row)
    warm = [r for r in result if r['temperature'] == 'warm']
    require(warm, 'Missing warm LIST runs')
    summary = dict(load_ms=statistics.median(r['load_ms'] for r in warm),
        command_ms=statistics.median(r['command_ms'] for r in warm),
        load_range_ms=[min(r['load_ms'] for r in warm), max(r['load_ms'] for r in warm)])
    report = dict(status='pass', tier='development', transport='IDE' if manifest.get('ide_only') else 'SIO',
        scope='LIST >NIL: at root, one cold and repeated warm runs on the unchanged packaged VBXE shell. '
              'Elapsed guest times include interrupts/preemption. Each direct partition reconciles separately; '
              'nested reader and validation totals must not be added to their parents.',
        summary=summary, rows=result, runtime=record['runtime'], rom=record['rom'], machine=record['machine'],
        input=record['benchmark_input'], source_inputs=manifest['source_inputs'], compiler=program['build']['revision'],
        bank_zero_delta=dict(fixed=0, per_task=0, idle=0),
        hashes=dict(observer=sha256(Path(__file__)), fixture=sha256(Path(listing.__file__)),
            decoder=definition['decoder_sha256'], xex=sha256(bundle/'program.xex'),
            manifest=sha256(bundle/'demo-manifest.json'), media=sha256(media),
            trace=sha256(bundle/'emulator.log'), run=sha256(output/'run.json')))
    (output/'loading.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)
    for name, phase in warm[0]['partitions'].items():
        print(name, json.dumps(phase), flush=True)
    return report


def run(bundle, output, repeats=3, media=None):
    require(repeats >= 1, 'Need a warm repetition')
    for path, digest in listing.LAYOUT_INPUTS.items():
        require(sha256(ROOT/path) == digest, 'Changed private cache layout: '+path)
    output.mkdir(parents=True, exist_ok=True)
    copied = output/'bundle'
    require(not copied.exists(), 'Choose a fresh loading output directory')
    shutil.copytree(bundle, copied, symlinks=True, ignore=shutil.ignore_patterns('emulator.log', 'pixels-*'))
    program = read_build(copied)
    require(program['build']['optimize'], 'Measure optimized loader')
    definition = markers(program)
    (output/'markers.json').write_text(json.dumps(definition, indent=2)+'\n')
    media = media or copied/'system.atr'
    manifest = json.loads((copied/'demo-manifest.json').read_text())
    override = media if not manifest.get('ide_only') and media != copied/'system.atr' else None
    integration = SimpleNamespace(exercise=lambda c:listing.exercise(c, media, repeats, [('LIST', '', True)], False))
    previous = {key:os.environ.get(key) for key in ENV}
    try:
        listing.observe(definition['marks'])
        record = listing.test_demo.run(copied, boot_smoke=True, measurement_commands=[], profile_commands=True,
            integration=integration, media_path=override,
            measurement_media_sha256=sha256(override) if override else None)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    record['benchmark_input'] = 'Prefilled empty cooked line, physical Return; ordinary Drain/dispatch'
    record['scope'] = 'Optimized packaged VBXE shell: LIST >NIL: loading profile, cold/warm caches, ownership/pixels/guards and EXIT restoration'
    (output/'run.json').write_text(json.dumps(record, indent=2)+'\n')
    return analyze(output, media)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--media', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--analyze', action='store_true')
    args = parser.parse_args()
    selected_media = args.media.resolve() if args.media else None
    if args.analyze:
        analyze(args.output.resolve(), selected_media)
    else:
        run(args.bundle.resolve(), args.output.resolve(), args.repeats, selected_media)
