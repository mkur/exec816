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
from package_demo import package
from library_paths import read_source
from native_program import ROOT, build, compiler, require, sha256


def bundle(output,compiler_dir,filesystem='sdfs',sector_bytes=128,gem_vdi=False):
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(compiler_dir)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==pin['emulator']['sha256'] and sha256(rom)==pin['rom']['sha256'],'Install the pinned paced bridge and ROM before building the demo')
    media=output/'media';media.mkdir(exist_ok=True)
    commands={}
    for name in ('HELLO','CAT','WC'):
        commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',media/name)
        (media/(name+'.options.json')).rename(output/(name+'.options.json'))
        (media/(name+'.profile.json')).rename(output/(name+'.profile.json'))
    sources=sorted(p for p in (ROOT/'examples/demo-disk').rglob('*') if p.is_file())
    for source in sources:
        # The media builder normalizes source text to LF; binary commands are exact.
        target=media/source.relative_to(ROOT/'examples/demo-disk')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(source.read_text(encoding='ascii'),encoding='ascii')
    require({p.relative_to(media).as_posix() for p in media.rglob('*') if p.is_file()}==set(commands)|{p.relative_to(ROOT/'examples/demo-disk').as_posix() for p in sources},'Unexpected stale file in demo media directory')
    disk_name='system.atr'
    proof_name=Path(disk_name).with_suffix('.verification.json').name
    try:files=make(output/disk_name,media,binary_names=set(commands),filesystem=filesystem,sector_bytes=sector_bytes)
    except StopIteration as error:raise ValueError('Demo media does not fit the 720-sector data ATR') from error
    config=ROOT/('config/shell-sdfs-256.json' if filesystem=='sdfs' and sector_bytes==256 else f'config/shell-{filesystem}.json')
    mount_config=json.loads(config.read_text())
    mounts=mount_config['mounts']
    mounts[0]['sector_bytes']=sector_bytes
    # Compile from the staging directory so unrelated example filenames do not
    # shadow library modules (examples/console.act is a standalone application).
    source=output/'demo.act';source.write_text(read_source(ROOT/'examples/demo.act'))
    program=build(toolchain,source,output,optimize=True,tasks=True,
                  task_capacity=8,console=True,stack_checks=True,dos_mounts=mounts,system_mount=mount_config.get('system_mount'))
    guide=(ROOT/'docs/guides/demo.md').read_text().replace('../demo.png','demo.png').replace('../images/','images/').replace('read-only SDFS data disk',f'read-only {filesystem.upper()} data disk')
    (output/'README.md').write_text(guide)
    shutil.copyfile(ROOT/'docs/demo.png',output/'demo.png')
    (output/'images').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'docs/images/demo-boot.png',output/'images/demo-boot.png')
    record=dict(format='exec816-demo-v1',tier='development',kernel=program['build'],pin=pin,
        configuration={**pin['configuration'],'diskemu':'generic56k'},mounts=mounts,commands=commands,
        media=disk_name,filesystem=filesystem,sector_bytes=sector_bytes,
        boot_image='of816/Exec-of816.xex',boot_manifest='of816/of816.json',
        distribution='exec816-demo.zip',
        artifacts={name:sha256(output/name) for name in ('program.xex',disk_name,'README.md',*([proof_name] if filesystem=='sdfs' else []))},
        files={name:dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                        **({} if name in commands else dict(lines=payload.count(b'\n'),words=len(payload.split()))))
               for name,payload in files.items()},
        source_inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                       [ROOT/'examples/demo.act',ROOT/'examples/demo-session.inc',ROOT/'examples/shell/shell-session.inc',
                        ROOT/'examples/shell/shell-commands.inc',ROOT/'examples/shell/shell-redirection.inc',ROOT/'examples/shell/shell-boot.inc',
                        ROOT/'docs/guides/demo.md',ROOT/'docs/demo.png',ROOT/'docs/images/demo-boot.png',ROOT/'docs/demo-distribution.txt',
                        ROOT/'tools/package_demo.py',ROOT/'LICENSE',ROOT/'LICENSE-MIT',ROOT/'LICENSING.md',
                        config,ROOT/'tools/build_command.py',
                        ROOT/'tools/make_data_disk.py',ROOT/'tools/sdfs_reference.py',ROOT/'tools/sdfs_reference.cpp',
                        ROOT/'tools/make_shell_disk.py',Path(__file__),*sources,
                        *sorted((ROOT/'lib/dos').glob('*.act'))]},
        bank_zero_delta=bank_zero_delta(program['build']['memory']),task_capacity=8,expected_peak_tasks=7,
        qualification='Focused development checks only; full release and general compiler qualification remain separate.')
    graphics=None
    if gem_vdi:
        from build_gem_artifact import build as build_graphics
        graphics=output/'gem-vdi'
        record['graphics']=build_graphics(graphics)
    (output/'demo-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    # OF816 records this final manifest, including the optional artifact.
    build_monitor(output/'of816',output,ROOT/'build/of816-upstream')
    package(output/'of816',output/record['distribution'],graphics)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--format',choices=('sdfs','mydos'),default='sdfs')
    parser.add_argument('--sector-bytes',type=int,choices=(128,256),default=128)
    parser.add_argument('--gem-vdi',action='store_true',help='Include the separately selected VBXE graphics workload')
    args=parser.parse_args();result=bundle(args.output,args.compiler_dir,args.format,args.sector_bytes,args.gem_vdi)
    print(f'Demo distribution ready: {args.output}/{result["distribution"]}')
