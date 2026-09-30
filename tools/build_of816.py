#!/usr/bin/env python3
"""Append a pinned OF816 boot monitor to an existing hosted Exec XEX."""
import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path

from native_program import ROOT, command, read_build, require, sha256, xex_segment
from boot_config import ABI as BOOT_ABI, files as boot_files, valid_blocks

PIN = json.loads((ROOT/'toolchain/of816.json').read_text())
ROM_PIN = json.loads((ROOT/'toolchain/altirra.json').read_text())['rom']
PORT = ROOT/'platform/of816'


def xex_segments(raw):
    require(raw[:2] == b'\xff\xff', 'Expected XEX executable')
    offset = 2
    while offset < len(raw):
        require(offset+4 <= len(raw), 'Truncated XEX segment header')
        low, high = struct.unpack_from('<HH', raw, offset)
        offset += 4
        require(low <= high and offset+high-low+1 <= len(raw), 'Truncated XEX segment')
        yield low, raw[offset:offset+high-low+1]
        offset += high-low+1


def boot_layout(program):
    """Borrow only idle-before-start Task arenas and currently free upper banks."""
    memory = program['build']['memory']
    boot = memory.get('boot_config', {})
    require(boot.get('abi') == BOOT_ABI, 'Incompatible Exec boot configuration ABI')
    low, high = memory['regions']['boot-state']
    require(boot.get('address') == low+BOOT_ABI['boot_state_offset'] and
            boot['address']+BOOT_ABI['size'] <= high and
            valid_blocks(boot.get('cache_blocks')), 'Invalid Exec boot configuration layout')
    from generate_dos_mounts import select_system, validate_mounts
    selection=select_system(validate_mounts(program['build']['dos_mounts']),program['build'].get('system_mount'))
    require(all(boot.get(key)==value for key,value in selection.items()),
            'Inconsistent packaged system-volume selection')
    root = memory['task_pools'][0]
    require(program['build']['tasks'] and program['build']['banked'], 'Native Task image required')
    require(root['dp'] == 0x2200 and root['stack_base'] == 0x4200 and
            root.get('stack_bytes',1536) == 1536, 'Root Task pool changed')
    # The kernel stack is idle until native startup. Unlike a worker stack it
    # retains enough room for the adapter and its caller stack in both profiles.
    kernel_low, kernel_high = memory['regions']['kernel-stack']
    require(kernel_high-kernel_low == 1568, 'Kernel stack reservation changed')
    c = memory['constants']
    seed = (program['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    free = [bank for bank in memory['usable_banks'] if seed[4*bank:4*bank+4] == b'\1\0\0\0']
    require(len(free) >= 2, 'OF816 needs two unused upper banks before handoff')
    layout = dict(OF_CODE=free[-1] << 16, OF_DATA=free[-2] << 16,
                  OF_DP=root['dp'], OF_STACK=root['stack_base'], OF_ADAPTER=kernel_low+16,
                  OF_STAGE=c['STAGE'], EXEC_LOADER=program['labels']['loader_start'],
                  EXEC_OLD_MEMLO=c['OLD_MEMLO'])
    # Reject even one payload byte in an arena borrowed by the monitor.
    borrowed = [(root['dp']-16,root['dp']+272),
                (root['stack_base']-16,root['stack_base']+1552),
                (kernel_low,kernel_high)]
    require(all(high <= other_low or low >= other_high
                for index,(low,high) in enumerate(borrowed)
                for other_low,other_high in borrowed[index+1:]), 'Boot arenas overlap')
    for address, payload in xex_segments(Path(program['xex']).read_bytes()):
        require(all(address+len(payload) <= low or address >= high for low, high in borrowed),
                'Exec XEX payload overlaps boot-only Task storage')
    for region in (*program['image']['segments'], *program['image']['zero_fill']):
        address = region['address']
        size = len(region['bytes']) if 'bytes' in region else region['size']
        require(all(address+size <= low or address >= high for low, high in borrowed),
                'Exec image data overlaps boot-only Task storage')
    return layout


def build(output, exec_build, upstream):
    output = output.resolve()
    upstream = upstream.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rom = ROOT/'build/firmware/altirraos-816.rom'
    notice = rom.with_name('ALTIRRAOS-LICENSE.txt')
    require(rom.is_file() and notice.is_file(),
            'Build the pinned ROM and license notice with tools/build_rom.py first')
    require(rom.stat().st_size == ROM_PIN['bytes'] and sha256(rom) == ROM_PIN['sha256'],
            'AltirraOS ROM differs from toolchain/altirra.json')
    if not upstream.exists():
        command(['git', 'clone', '--depth', '1', PIN['repository'], upstream])
        if command(['git', '-C', upstream, 'rev-parse', 'HEAD']).strip() != PIN['revision']:
            command(['git', '-C', upstream, 'fetch', '--depth', '1', 'origin', PIN['revision']])
            command(['git', '-C', upstream, 'checkout', '--detach', PIN['revision']])
    revision = command(['git', '-C', upstream, 'rev-parse', 'HEAD']).strip()
    require(revision == PIN['revision'], 'OF816 checkout differs from toolchain/of816.json')
    require(not command(['git', '-C', upstream, 'status', '--porcelain']).strip(), 'OF816 checkout must be clean')
    program = read_build(exec_build.resolve())
    compiler_pin = json.loads((ROOT/'toolchain/actionc.json').read_text())
    require(program['build']['revision'] == compiler_pin['revision'], 'Exec compiler pin changed')
    media = None
    manifest_path = program['output']/'demo-manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        require(all(sha256(program['output']/name) == digest
                    for name,digest in manifest['artifacts'].items()), 'Changed standard shell bundle')
        name = manifest['media']
        require(Path(name).name == name, 'Companion disk must be a bundle-local file')
        source = program['output']/name
        if source.resolve() != (output/name).resolve():
            shutil.copyfile(source,output/name)
        media = dict(name=name,sha256=sha256(output/name),configuration=manifest['configuration'],
                     manifest_sha256=sha256(manifest_path),filesystem=manifest['filesystem'],
                     sector_bytes=manifest['sector_bytes'])
    layout = boot_layout(program)
    for name, content in boot_files(program['build']['memory']['boot_config']).items():
        (output/name).write_text(content)
    (output/'boot-layout.inc').write_text(''.join(f'{name} = ${value:06x}\n' for name,value in layout.items()))
    (output/'platform.inc').write_text('.define PLATFORM "Exec816 boot monitor"\n')
    # Reuse upstream defaults with the unused FCode evaluator omitted.
    config = (upstream/'inc/config.inc').read_text()
    require(config.count('.define include_fcode 1') == 1, 'OF816 configuration changed')
    (output/'config.inc').write_text(config.replace('.define include_fcode 1', '.define include_fcode 0'))
    command(['ca65', '-I', output, '-I', PORT, '-I', upstream/'inc',
             '-l', output/'forth.lst', '-o', output/'forth.o', upstream/'forth.s'])
    command(['ca65', '-I', output, '-l', output/'boot.lst', '-o', output/'boot.o', PORT/'boot.s'])
    (output/'boot.cfg').write_text(f'''MEMORY {{
    LOW: start=${layout['OF_ADAPTER']:x}, size=$4f0, file="{output/'boot.bin'}";
    UPPER: start=${layout['OF_CODE']:x}, size=$10000, file="{output/'forth.bin'}";
}}
SEGMENTS {{
    BOOT: load=LOW, type=ro;
    FSystem: load=UPPER, type=ro;
    ZEROPAGE: load=LOW, type=zp, optional=yes;
}}
''')
    command(['ld65', '-C', output/'boot.cfg', '-Ln', output/'boot.lbl', '-m', output/'boot.map',
             '-o', output/'unused.bin', output/'boot.o', output/'forth.o'])
    labels = {line.split()[2].lstrip('.'): int(line.split()[1],16)
              for line in (output/'boot.lbl').read_text().splitlines()}
    adapter = (output/'boot.bin').read_bytes()
    forth = (output/'forth.bin').read_bytes()
    require(len(adapter) <= 0x4f0 and 0 < len(forth) <= 65536, 'OF816 boot regions overflow')
    raw = Path(program['xex']).read_bytes()
    raw += xex_segment(layout['OF_ADAPTER'], adapter)
    raw += xex_segment(0x2e0, struct.pack('<H', labels['of_park']))
    for offset in range(0, len(forth), 256):
        page = forth[offset:offset+256]
        raw += xex_segment(labels['of_target'], (layout['OF_CODE']+offset).to_bytes(3, 'little'))
        raw += xex_segment(labels['of_count'], bytes([len(page) & 255]))
        raw += xex_segment(layout['OF_STAGE'], page)
        raw += xex_segment(0x2e2, struct.pack('<H', labels['of_load']))
    raw += xex_segment(0x2e0, struct.pack('<H', labels['of_start']))
    xex = output/'Exec-of816.xex'
    xex.write_bytes(raw)
    # Keep the pinned firmware and its redistribution notice beside the boot files.
    for source in (rom, notice):
        if source.resolve() != (output/source.name).resolve():
            shutil.copyfile(source, output/source.name)
    (output/'README.md').write_bytes((ROOT/'docs/guides/boot-monitor.md').read_bytes())
    inputs = [ROOT/'docs/guides/boot-monitor.md', *PORT.glob('*.s'), ROOT/'tools/build_of816.py', ROOT/'toolchain/of816.json',
              ROOT/'toolchain/altirra.json', ROOT/'tools/boot_config.py', ROOT/'abi/boot-v1.json']
    record = dict(format='exec816-of816-boot-v1', of816=PIN, exec_build=str(program['output']),
                  exec_xex_sha256=program['build']['xex_sha256'], xex_sha256=sha256(xex),
                  rom=dict(name=rom.name,bytes=ROM_PIN['bytes'],sha256=sha256(output/rom.name),
                           license=notice.name,license_sha256=sha256(output/notice.name)),
                  inputs={str(p.relative_to(ROOT)):sha256(p) for p in sorted(inputs)},
                  layout=layout, labels=labels, adapter_bytes=len(adapter), forth_bytes=len(forth),
                  boot_config=program['build']['memory']['boot_config'],
                  guide_sha256=sha256(output/'README.md'),
                  boot_definitions_sha256=sha256(output/'boot-config.inc'),
                  bank_zero_delta=dict(fixed=0,per_task=0), boot_only_reused_bank_zero_bytes=3424,
                  task_capacity=program['build']['task_storage']['CAPACITY'],media=media,
                  transient_upper_banks=[layout['OF_CODE'] >> 16,layout['OF_DATA'] >> 16],
                  assembler=command(['ca65','--version'],stderr=subprocess.STDOUT).strip(),
                  linker=command(['ld65','--version'],stderr=subprocess.STDOUT).strip())
    (output/'of816.json').write_text(json.dumps(record,indent=2)+'\n')
    # Preserve upstream's redistribution notice with the runnable bundle.
    (output/'OF816-LICENSE.txt').write_bytes((upstream/'LICENSE').read_bytes())
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exec-build', type=Path, default=ROOT/'build/demo')
    parser.add_argument('--upstream', type=Path, default=ROOT/'build/of816-upstream')
    parser.add_argument('--output', type=Path, default=ROOT/'build/demo/of816')
    args = parser.parse_args()
    result = build(args.output, args.exec_build, args.upstream)
    print('OF816 boot image:', args.output/'Exec-of816.xex', result['forth_bytes'], 'Forth bytes')
