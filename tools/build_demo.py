#!/usr/bin/env python3
"""Build a demo with OF816 boot, system disk and pinned AltirraOS ROM."""
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
from native_program import ROOT, build, compiler, read_build, require, sha256

DEMO_IMAGE_DATA_BYTES = 4096
WORK_SECTORS = 2880
WORK_SECTOR_BYTES = 256


def bundle(output,compiler_dir,filesystem='sdfs',sector_bytes=256,gem_vdi=False,bitmap_console=False,bitmap_shell_only=False,desktop=False,system_kib=720,text_shell_only=False):
    if desktop:
        bitmap_shell_only=True
    require(not (bitmap_shell_only and (gem_vdi or bitmap_console)),
            'The shell-only bitmap demo is a standalone boot selection')
    require(not (text_shell_only and (bitmap_shell_only or gem_vdi or bitmap_console)),
            'The shell-only text demo is a standalone boot selection')
    shell_only=bitmap_shell_only or text_shell_only
    require(system_kib in (360,720),'System disk must be 360 or 720 KiB')
    system_sectors=system_kib*1024//sector_bytes
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(compiler_dir)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==pin['emulator']['sha256'] and sha256(rom)==pin['rom']['sha256'],'Install the pinned paced bridge and ROM before building the demo')
    media=output/'media';media.mkdir(exist_ok=True)
    command_dir=media/'C';command_dir.mkdir(exist_ok=True)
    commands={}
    for name in ('HELLO','CAT','WC','CMP','CKSUM','HEXDUMP','HEAD','TAIL','FIND','GREP','LIST','MORE','COPY','TEE','DELETE','RENAME','MAKEDIR','ASSIGN','PRIMES'):
        commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',command_dir/name)
        (command_dir/(name+'.options.json')).rename(output/(name+'.options.json'))
        (command_dir/(name+'.profile.json')).rename(output/(name+'.profile.json'))
    binary_names={f'C/{name}' for name in commands}
    sources=sorted(p for p in (ROOT/'examples/demo-disk').rglob('*') if p.is_file())
    for source in sources:
        # The media builder normalizes source text to LF; binary commands are exact.
        target=media/source.relative_to(ROOT/'examples/demo-disk')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(source.read_text(encoding='ascii'),encoding='ascii')
    if shell_only:
        title='bitmap' if bitmap_shell_only else 'text'
        dimensions='80 by 30' if bitmap_shell_only else '40 by 24'
        (media/'README.TXT').write_text(f'Exec816 {title} shell\n\n'
            f'The full {dimensions} screen is your shell.\nNo prime task is started.\n\n'
            'Try TASKS, DIR, MEM, HELLO | WC,\nand CAT STORY.TXT | WC.\n'
            'RUN PRIMES opens a lower pane. JOBS shows its identity;\n'
            'BREAK identity stops it. PRIMES PASSES 1 runs one foreground pass.\n'
            'EXIT returns to the OS.\n',encoding='ascii')
    if desktop:
        (media/'README.TXT').write_text('Exec816 desktop preview\n\nA 64 by 20 shell and an independent application.\nST mouse, port 1, left button.\nDrag titles; Escape cancels a drag.\nControl Panel: Toggle, Small/Large, Apply and Cancel.\nTab/Shift-Tab: focus; Space: activate; Return: Apply.\nEscape/BREAK: cancel. Locked is disabled.\nIts X gadget closes only that app.\nClick the shell to type. EXIT closes the desktop.\nNo primes. SYS: is read-only; WORK: in D8 is writable.\n',encoding='ascii')
    require({p.relative_to(media).as_posix() for p in media.rglob('*') if p.is_file()}==binary_names|{p.relative_to(ROOT/'examples/demo-disk').as_posix() for p in sources},'Unexpected stale file in demo media directory')
    disk_name='system.atr'
    proof_name=Path(disk_name).with_suffix('.verification.json').name
    try:files=make(output/disk_name,media,binary_names=binary_names,filesystem=filesystem,
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
    make(output/'work.atr',workspace,filesystem=filesystem,
         sector_bytes=WORK_SECTOR_BYTES,sectors=WORK_SECTORS)
    mounts.append(dict(alias='WORK',unit=56,sectors=WORK_SECTORS,sector_bytes=WORK_SECTOR_BYTES,
                       profile=4,format=1 if filesystem=='mydos' else 2,access='readwrite'))
    # Compile from the staging directory so unrelated example filenames do not
    # shadow library modules (examples/console.act is a standalone application).
    entry=ROOT/('examples/desktop.act' if desktop else 'examples/shell/shell.act' if shell_only else 'examples/demo.act')
    source=output/'demo.act';source.write_text(read_source(entry))
    # Shared fault strings and the composed shell/client globals need 4 KiB.
    # All demo variants use the same explicit upper-RAM arena; bank zero is unchanged.
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text())
    profile['image_data_bytes']=DEMO_IMAGE_DATA_BYTES
    memory_profile=output/'demo-memory.json'
    memory_profile.write_text(json.dumps(profile,indent=2)+'\n')
    if bitmap_shell_only:
        from build_bitmap_console import build_bitmap
        from build_bitmap_artifact import copy_notices
        program=build_bitmap(source,output/'bitmap-console',program_output=output,
            compiler_dir=compiler_dir,desktop=desktop,stack_checks=True,dos_mounts=mounts,
            system_mount=mount_config.get('system_mount'),memory_profile=memory_profile)
        copy_notices(output/'bitmap-console/selected',output)
        pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
    else:
        program=build(toolchain,source,output,optimize=True,tasks=True,
                      task_capacity=8,console=True,stack_checks=True,dos_mounts=mounts,
                      system_mount=mount_config.get('system_mount'),memory_profile=memory_profile)
    guide=(ROOT/'docs/guides/demo.md').read_text().replace('../demo.png','demo.png').replace('../images/','images/')
    system_name='SDFS 2.1' if filesystem=='sdfs' else 'MyDOS'
    default_geometry=('The supplied SDFS 2.1 system disk has 2,880 sectors of 256 bytes (720 KiB\n'
        'nominal capacity), equivalent to 80 tracks, two sides and 18 sectors per track. The\n'
        'disposable WORK: disk also has 2,880 sectors of 256 bytes (720 KiB nominal capacity).')
    require(default_geometry in guide,'Demo guide default geometry changed')
    track_geometry=', equivalent to 80 tracks, two sides and 18 sectors per track' if system_kib==720 and sector_bytes==256 else ''
    guide=guide.replace(default_geometry,
        f'The supplied {system_name} system disk has {system_sectors:,} sectors of {sector_bytes} bytes '
        f'({system_kib} KiB nominal capacity){track_geometry}. The disposable WORK: disk has '
        f'{WORK_SECTORS:,} sectors of {WORK_SECTOR_BYTES} bytes (720 KiB nominal capacity).')
    guide=guide.replace('720 KiB read-only SDFS data disk',
                        f'{system_kib} KiB read-only {system_name} data disk')
    if bitmap_shell_only:
        guide=(ROOT/'docs/bitmap-shell-distribution.txt').read_text().replace('@SYSTEM_DISK@',disk_name).replace('@SYSTEM_DRIVE@','1')
    if text_shell_only:
        guide=(ROOT/'docs/text-shell-distribution.txt').read_text().replace('@SYSTEM_DISK@',disk_name).replace('@SYSTEM_DRIVE@','1')
    if desktop:
        guide=(ROOT/'docs/desktop-distribution.txt').read_text().replace('@SYSTEM_DISK@',disk_name).replace('@SYSTEM_DRIVE@','1')
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
                               filesystem=filesystem,sectors=WORK_SECTORS,
                               sector_bytes=WORK_SECTOR_BYTES)],
        boot_image='of816/Exec-of816.xex',boot_manifest='of816/of816.json',
        distribution='exec816-demo.zip',
        artifacts={name:sha256(output/name) for name in ('program.xex',disk_name,'work.atr','README.md',*([proof_name] if filesystem=='sdfs' else []))},
        files={name:dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                        **({} if name in binary_names else dict(lines=payload.count(b'\n'),words=len(payload.split()))))
               for name,payload in files.items()},
        source_inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                       [ROOT/'examples/demo.act',ROOT/'examples/demo-session.inc',ROOT/'examples/shell/shell-session.inc',
                        ROOT/'examples/shell/shell-commands.inc',ROOT/'examples/shell/shell-redirection.inc',ROOT/'examples/shell/shell-path.inc',ROOT/'examples/shell/shell-jobs.inc',ROOT/'examples/shell/shell-execute.inc',ROOT/'examples/shell/shell-boot.inc',
                        *(ROOT/'examples/commands'/name for name in ('command-common.inc','command-files.inc','command-write.inc','command-transfer.inc','command-pattern.inc')),
                        ROOT/'docs/guides/demo.md',ROOT/'docs/demo.png',ROOT/'docs/images/demo-boot.png',ROOT/'docs/demo-distribution.txt',
                        ROOT/'tools/package_demo.py',ROOT/'LICENSE',ROOT/'LICENSE-MIT',ROOT/'LICENSING.md',
                        config,ROOT/'tools/build_command.py',
                        ROOT/'tools/make_data_disk.py',ROOT/'tools/sdfs_reference.py',ROOT/'tools/sdfs_reference.cpp',
                        ROOT/'tools/make_shell_disk.py',Path(__file__),*sources,
                        *sorted((ROOT/'lib/dos').glob('*.act'))]},
        bank_zero_delta=bank_zero_delta(program['build']['memory']),task_capacity=8,expected_peak_tasks=7,
        qualification='Focused development checks only; full release and general compiler qualification remain separate.')
    if text_shell_only:
        record.update(shell_only=True,expected_peak_tasks=6)
        record['source_inputs'].update({str(path.relative_to(ROOT)):sha256(path) for path in (
            entry,ROOT/'docs/text-shell-distribution.txt')})
    if bitmap_shell_only:
        record.update(bitmap=True,shell_only=True,desktop=desktop,expected_peak_tasks=7 if desktop else 6,
            font_source='bitmap-console/selected/src/vdi/font8x8.c')
        record['artifacts'].update({name:sha256(output/name) for name in GEM_NOTICES})
        record['source_inputs'].update({str(path.relative_to(ROOT)):sha256(path) for path in (
            entry,ROOT/'docs/bitmap-shell-distribution.txt',ROOT/'tools/build_bitmap_console.py',ROOT/'tools/build_bitmap_artifact.py')})
        record['drawing']=json.loads((output/'bitmap-console/c-image.json').read_text())['provenance']
    if desktop:
        record['source_inputs'].update({str(path.relative_to(ROOT)):sha256(path) for path in (
            ROOT/'docs/desktop-distribution.txt',*sorted((ROOT/'lib/desktop').glob('*.act')))})
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
            bitmap_shell=output if bitmap_shell_only else None,
            text_shell=output if text_shell_only else None)
    return record


def refresh_monitor(output):
    """Refresh boot assembly/guides around the verified existing native payload."""
    output=output.resolve()
    program=read_build(output)
    required=('loader_of_begin','loader_progress_add','loader_progress_finish')
    require(all(name in program['labels'] for name in required),
            'Rebuild the native demo first: current loader callbacks are required')
    path=output/'demo-manifest.json'
    record=json.loads(path.read_text())
    require(all(sha256(output/name)==digest for name,digest in record['artifacts'].items()),
            'Changed native demo artifacts')
    guides=[ROOT/'docs/guides/boot-monitor.md',ROOT/'docs/demo-distribution.txt']
    if record.get('shell_only'):
        guide=ROOT/('docs/desktop-distribution.txt' if record.get('desktop') else
                    'docs/bitmap-shell-distribution.txt' if record.get('bitmap') else
                    'docs/text-shell-distribution.txt')
        drive=program['build']['memory']['boot_config']['system_drive']
        (output/'README.md').write_text(guide.read_text().replace('@SYSTEM_DISK@',record['media'])
                                       .replace('@SYSTEM_DRIVE@',str(drive)))
        record['artifacts']['README.md']=sha256(output/'README.md')
        guides.append(guide)
    record['monitor_refresh']=dict(native_xex_sha256=sha256(output/'program.xex'),
        native_build_sha256=sha256(output/'build.json'),
        source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in
                       [Path(__file__),ROOT/'tools/build_of816.py',ROOT/'tools/banked_image.py',*guides]})
    path.write_text(json.dumps(record,indent=2)+'\n')
    build_monitor(output/'of816',output,ROOT/'build/of816-upstream')
    package(output/'of816',output/record['distribution'],
            output/'gem-vdi' if record.get('graphics') else None,
            output/'bitmap-console' if record.get('bitmap_console') else None,
            bitmap_shell=output if record.get('shell_only') and record.get('bitmap') else None,
            text_shell=output if record.get('shell_only') and not record.get('bitmap') else None)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--format',choices=('sdfs','mydos'),default='sdfs')
    parser.add_argument('--sector-bytes',type=int,choices=(128,256),default=256)
    parser.add_argument('--system-kib',type=int,choices=(360,720),default=720,
                        help='Nominal system disk capacity; WORK is always 720 KiB with 256-byte sectors')
    parser.add_argument('--gem-vdi',action='store_true',help='Include the separately selected VBXE graphics workload')
    parser.add_argument('--bitmap-console',action='store_true',help='Include the separately selected VBXE bitmap shell preview')
    parser.add_argument('--desktop',action='store_true',help='Autoboot a framed shell and independent graphical application with ST mouse input')
    parser.add_argument('--bitmap-shell-only',action='store_true',help='Autoboot OF816 into a full-screen VBXE shell without primes')
    parser.add_argument('--text-shell-only',action='store_true',help='Autoboot OF816 into a full-screen standard shell without primes')
    parser.add_argument('--refresh-monitor',action='store_true',help='Refresh OF816 and the ZIP around an existing verified native demo')
    parser.add_argument('--cartridge-from',type=Path,help='Add Atarimax boot images to an existing demo ZIP without rebuilding its XEX')
    parser.add_argument('--cartridge-source-sha256',help='Required checksum of the existing demo ZIP')
    args=parser.parse_args()
    if args.refresh_monitor:
        if args.cartridge_from or args.cartridge_source_sha256:
            parser.error('--refresh-monitor cannot be combined with --cartridge-from')
        refresh_monitor(args.output)
    elif args.cartridge_from:
        if not args.cartridge_source_sha256:
            parser.error('--cartridge-from requires --cartridge-source-sha256')
        from build_cartridge import augment_demo
        augment_demo(args.cartridge_from,args.output,args.cartridge_source_sha256)
    else:
        if args.cartridge_source_sha256:
            parser.error('--cartridge-source-sha256 requires --cartridge-from')
        bundle(args.output,args.compiler_dir,args.format,args.sector_bytes,args.gem_vdi,args.bitmap_console,args.bitmap_shell_only,desktop=args.desktop,system_kib=args.system_kib,text_shell_only=args.text_shell_only)
    print(f'Demo distribution ready: {args.output}/exec816-demo.zip')
