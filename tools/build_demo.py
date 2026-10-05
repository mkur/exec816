#!/usr/bin/env python3
"""Build the text-console demo with OF816 boot, system disk and pinned AltirraOS ROM."""
from stack_budget import bank_zero_delta
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from build_command import compile_command
from build_of816 import build as build_monitor
from make_data_disk import make
from package_demo import package,GEM_NOTICES
from library_paths import read_source
from native_program import ROOT, build, compiler, require, sha256

DEMO_IMAGE_DATA_BYTES = 4096


def bundle(output,compiler_dir,filesystem='sdfs',sector_bytes=256,gem_vdi=False,bitmap_console=False,bitmap_shell_only=False,system_kib=720):
    require(not (bitmap_shell_only and (gem_vdi or bitmap_console)),
            'The shell-only bitmap demo is a standalone boot selection')
    require(system_kib in (360,720),'System disk must be 360 or 720 KiB')
    system_sectors=system_kib*1024//sector_bytes
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(compiler_dir)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==pin['emulator']['sha256'] and sha256(rom)==pin['rom']['sha256'],'Install the pinned paced bridge and ROM before building the demo')
    media=output/'media';media.mkdir(exist_ok=True)
    commands={}
    for name in ('HELLO','CAT','WC','CMP','CKSUM','HEXDUMP','HEAD','GREP','LIST','MORE','COPY','TEE','DELETE','RENAME','MAKEDIR','ASSIGN'):
        commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',media/name)
        (media/(name+'.options.json')).rename(output/(name+'.options.json'))
        (media/(name+'.profile.json')).rename(output/(name+'.profile.json'))
    sources=sorted(p for p in (ROOT/'examples/demo-disk').rglob('*') if p.is_file())
    for source in sources:
        # The media builder normalizes source text to LF; binary commands are exact.
        target=media/source.relative_to(ROOT/'examples/demo-disk')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(source.read_text(encoding='ascii'),encoding='ascii')
    if bitmap_shell_only:
        (media/'README.TXT').write_text('Exec816 bitmap shell\n\n'
            'The full 80 by 30 screen is your shell.\nNo prime task is started.\n\n'
            'Try TASKS, DIR, MEM, HELLO | WC,\nand CAT STORY.TXT | WC.\n'
            'EXIT returns to the OS.\n',encoding='ascii')
    require({p.relative_to(media).as_posix() for p in media.rglob('*') if p.is_file()}==set(commands)|{p.relative_to(ROOT/'examples/demo-disk').as_posix() for p in sources},'Unexpected stale file in demo media directory')
    disk_name='system.atr'
    proof_name=Path(disk_name).with_suffix('.verification.json').name
    try:files=make(output/disk_name,media,binary_names=set(commands),filesystem=filesystem,
                   sector_bytes=sector_bytes,sectors=system_sectors)
    except StopIteration as error:raise ValueError('Demo media does not fit the system ATR') from error
    config=ROOT/('config/shell-sdfs-256.json' if filesystem=='sdfs' and sector_bytes==256 else f'config/shell-{filesystem}.json')
    mount_config=json.loads(config.read_text())
    mounts=mount_config['mounts']
    mounts[0]['sectors']=system_sectors
    mounts[0]['sector_bytes']=sector_bytes
    # Keep SYS read-only and provide explicitly disposable writable media.
    # D8 avoids colliding when the boot monitor selects D1..D7 for SYS.
    workspace=output/'workspace-source'
    workspace.mkdir(exist_ok=True)
    (workspace/'README.TXT').write_text('Disposable Exec816 WORK: disk.\n'
        'Copy this ATR before experimenting. Mount it in drive D8.\n',encoding='ascii')
    make(output/'work.atr',workspace,filesystem=filesystem,sector_bytes=128)
    mounts.append(dict(alias='WORK',unit=56,sectors=720,sector_bytes=128,
                       profile=4,format=1 if filesystem=='mydos' else 2,access='readwrite'))
    # Compile from the staging directory so unrelated example filenames do not
    # shadow library modules (examples/console.act is a standalone application).
    entry=ROOT/('examples/shell/shell.act' if bitmap_shell_only else 'examples/demo.act')
    source=output/'demo.act';source.write_text(read_source(entry))
    if bitmap_shell_only:
        from build_bitmap_console import build_bitmap
        from build_bitmap_artifact import copy_notices
        program=build_bitmap(source,output/'bitmap-console',program_output=output,
            compiler_dir=compiler_dir,stack_checks=True,dos_mounts=mounts,system_mount=mount_config.get('system_mount'))
        copy_notices(output/'bitmap-console/selected',output)
        pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
    else:
        # The shell/prime globals and shared fault strings exceed the default
        # 2 KiB arena. Reserve 4 KiB in upper RAM for this composed application;
        # fixed bank-zero and per-Task reservations remain unchanged.
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes']=DEMO_IMAGE_DATA_BYTES
        memory_profile=output/'demo-memory.json'
        memory_profile.write_text(json.dumps(profile,indent=2)+'\n')
        program=build(toolchain,source,output,optimize=True,tasks=True,
                      task_capacity=8,console=True,stack_checks=True,dos_mounts=mounts,
                      system_mount=mount_config.get('system_mount'),memory_profile=memory_profile)
    guide=(ROOT/'docs/guides/demo.md').read_text().replace('../demo.png','demo.png').replace('../images/','images/')
    system_name='SDFS 2.1' if filesystem=='sdfs' else 'MyDOS'
    default_geometry=('The supplied SDFS 2.1 system disk has 2,880 sectors of 256 bytes (720 KiB\n'
        'nominal capacity), equivalent to 80 tracks, two sides and 18 sectors per track. The\n'
        'disposable WORK: disk remains 720 sectors of 128 bytes (90 KiB).')
    require(default_geometry in guide,'Demo guide default geometry changed')
    track_geometry=', equivalent to 80 tracks, two sides and 18 sectors per track' if system_kib==720 and sector_bytes==256 else ''
    guide=guide.replace(default_geometry,
        f'The supplied {system_name} system disk has {system_sectors:,} sectors of {sector_bytes} bytes '
        f'({system_kib} KiB nominal capacity){track_geometry}. The disposable WORK: disk remains '
        '720 sectors of 128 bytes (90 KiB).')
    guide=guide.replace('720 KiB read-only SDFS data disk',
                        f'{system_kib} KiB read-only {system_name} data disk')
    if bitmap_shell_only:
        guide=(ROOT/'docs/bitmap-shell-distribution.txt').read_text().replace('@SYSTEM_DISK@',disk_name).replace('@SYSTEM_DRIVE@','1')
    (output/'README.md').write_text(guide)
    shutil.copyfile(ROOT/'docs/demo.png',output/'demo.png')
    (output/'images').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'docs/images/demo-boot.png',output/'images/demo-boot.png')
    record=dict(format='exec816-demo-v1',tier='development',kernel=program['build'],pin=pin,
        configuration={**pin['configuration'],'diskemu':'generic56k'},mounts=mounts,commands=commands,
        media=disk_name,filesystem=filesystem,sector_bytes=sector_bytes,
        system_kib=system_kib,system_sectors=system_sectors,
        additional_media=[dict(name='work.atr',sha256=sha256(output/'work.atr'),
                               drive=8,alias='WORK',access='readwrite',
                               filesystem=filesystem,sector_bytes=128)],
        boot_image='of816/Exec-of816.xex',boot_manifest='of816/of816.json',
        distribution='exec816-demo.zip',
        artifacts={name:sha256(output/name) for name in ('program.xex',disk_name,'work.atr','README.md',*([proof_name] if filesystem=='sdfs' else []))},
        files={name:dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                        **({} if name in commands else dict(lines=payload.count(b'\n'),words=len(payload.split()))))
               for name,payload in files.items()},
        source_inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                       [ROOT/'examples/demo.act',ROOT/'examples/demo-session.inc',ROOT/'examples/shell/shell-session.inc',
                        ROOT/'examples/shell/shell-commands.inc',ROOT/'examples/shell/shell-redirection.inc',ROOT/'examples/shell/shell-path.inc',ROOT/'examples/shell/shell-boot.inc',
                        *(ROOT/'examples/commands'/name for name in ('command-common.inc','command-files.inc','command-write.inc','command-transfer.inc','command-pattern.inc')),
                        ROOT/'docs/guides/demo.md',ROOT/'docs/demo.png',ROOT/'docs/images/demo-boot.png',ROOT/'docs/demo-distribution.txt',
                        ROOT/'tools/package_demo.py',ROOT/'LICENSE',ROOT/'LICENSE-MIT',ROOT/'LICENSING.md',
                        config,ROOT/'tools/build_command.py',
                        ROOT/'tools/make_data_disk.py',ROOT/'tools/sdfs_reference.py',ROOT/'tools/sdfs_reference.cpp',
                        ROOT/'tools/make_shell_disk.py',Path(__file__),*sources,
                        *sorted((ROOT/'lib/dos').glob('*.act'))]},
        bank_zero_delta=bank_zero_delta(program['build']['memory']),task_capacity=8,expected_peak_tasks=7,
        qualification='Focused development checks only; full release and general compiler qualification remain separate.')
    if bitmap_shell_only:
        record.update(bitmap=True,shell_only=True,expected_peak_tasks=6,
            font_source='bitmap-console/selected/src/vdi/font8x8.c')
        record['artifacts'].update({name:sha256(output/name) for name in GEM_NOTICES})
        record['source_inputs'].update({str(path.relative_to(ROOT)):sha256(path) for path in (
            entry,ROOT/'docs/bitmap-shell-distribution.txt',ROOT/'tools/build_bitmap_console.py',ROOT/'tools/build_bitmap_artifact.py')})
        record['drawing']=json.loads((output/'bitmap-console/c-image.json').read_text())['provenance']
    graphics=None
    if gem_vdi:
        from build_gem_artifact import build as build_graphics
        graphics=output/'gem-vdi'
        record['graphics']=build_graphics(graphics)
    (output/'demo-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    bitmap=None
    if bitmap_console:
        from build_bitmap_artifact import build as build_bitmap
        bitmap=output/'bitmap-console'
        record['bitmap_console']=build_bitmap(bitmap,output)
        (output/'demo-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    # OF816 records this final manifest, including the optional artifact.
    build_monitor(output/'of816',output,ROOT/'build/of816-upstream')
    package(output/'of816',output/record['distribution'],graphics,bitmap,
            bitmap_shell=output if bitmap_shell_only else None)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--format',choices=('sdfs','mydos'),default='sdfs')
    parser.add_argument('--sector-bytes',type=int,choices=(128,256),default=256)
    parser.add_argument('--system-kib',type=int,choices=(360,720),default=720,
                        help='Nominal system disk capacity; WORK remains 720 sectors')
    parser.add_argument('--gem-vdi',action='store_true',help='Include the separately selected VBXE graphics workload')
    parser.add_argument('--bitmap-console',action='store_true',help='Include the separately selected VBXE bitmap shell preview')
    parser.add_argument('--bitmap-shell-only',action='store_true',help='Autoboot OF816 into a full-screen VBXE shell without primes')
    args=parser.parse_args();result=bundle(args.output,args.compiler_dir,args.format,args.sector_bytes,args.gem_vdi,args.bitmap_console,args.bitmap_shell_only,args.system_kib)
    print(f'Demo distribution ready: {args.output}/{result["distribution"]}')
