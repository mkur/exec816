#!/usr/bin/env python3
"""Measure bounded public MyDOS operations using the existing emitted harness."""
import argparse
import json
import shutil
import time
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from library_paths import library_file, read_source
from measure_write_performance import instrument
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN
from os_boundary import emulator
from filesystem_audit import Audit

CASES = ('create', 'warm-read', 'writable-open', 'same-sector-seeks',
         'forward-seeks', 'unknown-end', 'known-end-read', 'listing',
         'repeat-listing', 'truncate', 'delete', 'mkdir', 'rmdir','examine-exact')
COLUMNS = ('frames', 'kernel_calls', 'physical_reads', 'physical_writes',
           'write_logical_reads', 'payload_visits', 'read_logical_fetches',
           'cache_hits', 'chain_visits', 'bitmap_loads')


def run(out, size, from_build=None, frozen=None, accurate=False, hint=4, cache_blocks=None):
    out.mkdir(parents=True, exist_ok=True)
    instrument(out, frozen)
    probe = out/'writeperfprobe.act'
    probe.write_text(probe.read_text().replace('PUBLIC BYTE armed',
        'PUBLIC LONGCARD chainVisits,bitmapLoads,directoryLoads\nPUBLIC BYTE armed', 1))
    probe.write_text(probe.read_text().replace('ENDMODULE', 'PUBLIC CARD FUNC Frame()\n\nRETURN(clock)\n\nENDMODULE'))
    source = frozen/'lib/mydos/mydosfile.act' if frozen and (frozen/'lib/mydos/mydosfile.act').exists() else library_file('mydosfile.act')
    text = read_source(source)
    require(text.count('  chain.hops==+1') == 1, 'Changed chain-visit observer')
    text = text.replace('USE FSSTATUS\n', 'USE FSSTATUS\nUSE WRITEPERFPROBE\n', 1)
    text = text.replace('  chain.hops==+1',
        '  IF WRITEPERFPROBE.active<>0 THEN WRITEPERFPROBE.chainVisits==+1 FI\n  chain.hops==+1', 1)
    (out/'mydosfile.act').write_text(text)
    io = out/'fswriteio.act'
    text = io.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE MYDOSTYPES\n', 1)
    marker = '  LET status=BLOCKIO.BeginFetch('
    require(text.count(marker) == 1, 'Changed bitmap-load observer')
    text = text.replace(marker, '''  IF WRITEPERFPROBE.active<>0 THEN
    BEGIN
      LET native=MYDOSTYPES.Volume POINTER(service.work.volume.state)
      IF sector>=native.vtocLow AND sector<=360 THEN
        WRITEPERFPROBE.bitmapLoads==+1
      FI
    END
  FI
'''+marker, 1)
    io.write_text(text)
    fsio = out/'fsio.act'
    text = read_source(frozen/'lib/fs/fsio.act' if frozen and (frozen/'lib/fs/fsio.act').exists() else library_file('fsio.act'))
    text = text.replace('USE FSSTATUS\n','USE FSSTATUS\nUSE WRITEPERFPROBE\n',1)
    require(text.count('  service.work.operations==+1') == 1,
            'Changed directory-fetch observer')
    text = text.replace('  service.work.operations==+1',
        '  IF WRITEPERFPROBE.active<>0 AND service.work.neededSector>=service.work.directory\n'
        '      AND LONGCARD(service.work.neededSector)<=LONGCARD(service.work.directory)+7 THEN\n'
        '    WRITEPERFPROBE.directoryLoads==+1\n  FI\n  service.work.operations==+1',1)
    fsio.write_text(text)
    fixture = out/'mydos_performance.act'
    fixture.write_text(read_source(ROOT/'tests/programs/mydos_performance.act').replace(
        'allocationHint=4', f'allocationHint={hint}'))
    media = out/'volume.atr'
    template = ROOT/f'tests/fixtures/filesystem-write/mydos-{size}.atr'
    shutil.copyfile(template, media)
    initial = Audit(media.read_bytes()); initial.mydos()
    mounts = [dict(alias='D1', unit=49, sectors=initial.image.count,
                   sector_bytes=size, format=1, profile=4, access='readwrite')]
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    (out/'memory-profile.json').write_text(json.dumps(profile)+'\n')
    program = read_build(from_build) if from_build else build(
        compiler(ROOT/'build/actionc', release=True), fixture, out,
        optimize=True, tasks=True, task_capacity=8, dos_mounts=mounts,
        console_deferred=True, memory_profile=out/'memory-profile.json',
        image_data=[(0x2dffd0, bytes([0xa5])*(16384+64)), (0x320000, bytes(8192))])
    if from_build:
        for group in ('platform_inputs','task_inputs','console_inputs','banked_inputs'):
            for name,digest in program['build'].get(group,{}).items():
                original=frozen/name if frozen and (frozen/name).exists() else ROOT/name
                require(sha256(original)==digest,'Changed operation input: '+name)
        require(program['build']['source_sha256'] == sha256(fixture), 'Changed operation fixture')
        for path in out.glob('*.act'):
            require((from_build/path.name).exists() and sha256(path) == sha256(from_build/path.name),
                    'Changed operation observer: '+path.name)
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        configuration = {**PIN['configuration'], 'diskemu': 'generic56k', 'accuratedisk': accurate}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        def before(b):
            b.mount(0, str(media))
            if cache_blocks is not None:
                boot=program['build']['memory']['boot_config']
                b.memload(boot['address']+boot['abi']['fields']['cache_blocks'],
                          cache_blocks.to_bytes(2,'little'))
            trace = next(d['address'] for d in program['image']['data'] if '_WRITEPERFPROBE_TRACE_' in d['name'])
            b.memload(trace, (0x320000).to_bytes(3, 'little'))
        runtime, _ = execute(bridge, program, before_run=before, timeout=600, frame_limit=30000)
        ownership(bridge, program, out)
        view = {**program['image'], 'data': [d for d in program['image']['data'] if '_MYDOSPERFORMANCE_' in d['name']]}
        raw = bytes(data(bridge, view, 'rows'))
        values = [int.from_bytes(raw[i:i+4], 'little') for i in range(0, len(raw), 4)]
        rows = {name: dict(zip(COLUMNS, values[index*len(COLUMNS):(index+1)*len(COLUMNS)]))
                for index, name in enumerate(CASES)}
        layouts = data(bridge, view, 'layouts', True)
        def wide(name):
            raw=bytes(data(bridge,view,name))
            return [int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
        first_rows=wide('firstRowFrames');directory_fetches=wide('directoryFetches')
        for i,name in enumerate(('listing','repeat-listing')):
            require(rows[name]['read_logical_fetches'] >= directory_fetches[i],
                    'Directory-fetch counter exceeds total fetches')
            if frozen is None:
                require(rows[name]['chain_visits'] == 0 and
                        rows[name]['read_logical_fetches'] == directory_fetches[i],
                        'Ordinary listing measured a selected file')
        from banked_test_memory import read
        guard = read(bridge, 0x2dffd0, 16384+64, out)
        require(guard[:32] == guard[-32:] == bytes([0xa5])*32, 'Operation buffer guard changed')
        time.sleep(3); bridge.regs(); bridge._cmd_ok('EJECT drive=0')
    final = Audit(media.read_bytes()); final.mydos()
    require(final.files == initial.files, 'Operation fixture changed unrelated files')
    result = dict(status='pass', tier='development', rows=rows, layouts=layouts,
                  build=program['build'], machine=machine, configuration=configuration,
                  runtime=runtime, cache_blocks_override=cache_blocks,
                  source_sha256=sha256(template), media_sha256=sha256(media),
                  observer_inputs={p.name: sha256(p) for p in out.glob('*.act')},
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0),
                  listing_details={name:dict(first_metadata_frame=first_rows[i],
                      directory_fetches=directory_fetches[i],
                      selected_file_fetches=rows[name]['read_logical_fetches']-directory_fetches[i],
                      output_calls=0) for i,name in enumerate(('listing','repeat-listing'))},
                  emitted_body_bytes=sum(r['size'] for r in program['image']['routines']))
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    for name, counts in rows.items():
        print(name, counts, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, choices=(128, 256), default=128)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--frozen-sources', type=Path)
    parser.add_argument('--accurate-media', action='store_true')
    parser.add_argument('--hint', type=int, default=4)
    parser.add_argument('--cache-blocks', type=int)
    args = parser.parse_args()
    run(args.output.resolve(), args.size, args.from_build, args.frozen_sources,
        args.accurate_media, args.hint, args.cache_blocks)
