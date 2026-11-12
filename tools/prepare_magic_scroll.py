#!/usr/bin/env python3
"""Prepare the original MagiC MGVIEW binary and the shared viewer for scrolling."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from prepare_st_reference import ROOT, ADAPTER, run, sha256
from prepare_magic_text import prepare as prepare_text, controlled, reports, wait_for


def prepare(args):
    output=args.output.resolve()
    ported=output/'ported'
    setup=copy.copy(args);setup.output=ported
    record=prepare_text(setup)
    sdk=args.cache.resolve()/'sdk'
    cc,ld=sdk/'bin/m68k-atari-tos-gnu-gcc',sdk/'bin/m68k-atari-tos-gnu-ld'
    native=output/'mgview';native.mkdir(exist_ok=True)
    shutil.copytree(ported/'drive-c',native/'drive-c',dirs_exist_ok=True)
    shutil.copyfile(ported/'documents.st',native/'documents.st')
    original=ported/'inputs/MAGIC.A/GEMSYS/GEMDESK/MGVIEW.APP'
    run(['mcopy','-o','-i',native/'documents.st',original,'::MGVIEW.APP'])
    extracted=subprocess.run(['mtype','-i',str(native/'documents.st'),'::MGVIEW.APP'],
        capture_output=True,check=True).stdout
    if hashlib.sha256(extracted).hexdigest()!=sha256(original):
        raise RuntimeError('The floppy does not contain the unchanged MGVIEW binary')
    profiles={}
    libgcc=run(['m68k-elf-gcc','-m68000','-print-libgcc-file-name'])
    objects=ported/'objects'
    # The diagnostic wrapper normally logs every paint. Keep only startup
    # observation in the comparison, so scrolling performs no observer file I/O.
    run([cc,'-O2','-Wall','-DREFERENCE_SCROLL_COMPARE=1',
        '-I'+str(ADAPTER/'include'),'-I'+str(ROOT/'c/include'),'-I'+str(ROOT),
        '-c',ADAPTER/'text-main.c','-o',objects/'comparison-main.o'],
        output/'ported-observer-compile.log')
    wrappers=('evnt_multi','wind_update','wind_set','v_opnvwk','menu_bar','fsel_exinput','appl_exit')
    run([ld,'--gc-sections','-o',ported/'drive-c/TEXT.PRG',
        *('--wrap='+name for name in wrappers),objects/'comparison-main.o',
        *(objects/(name+'.o') for name in ('text','document','platform','path_helpers','bindings')),
        libgcc,'-L'+str(sdk/'lib'),'-lc',libgcc],output/'ported-observer-link.log')
    for name,directory in (('ported',ported),('mgview',native)):
        obj=output/(name+'-launcher.o')
        options=['-DREFERENCE_SCROLL_COMPARE=1']
        if name=='mgview': options.append('-DREFERENCE_MGVIEW=1')
        run([cc,'-O2','-Wall',*options,'-c',ADAPTER/'text-launcher.c','-o',obj],
            output/(name+'-compile.log'))
        launcher=directory/'drive-c/GEMSYS/GEMDESK/MAGXDESK.APP'
        run([ld,'-o',launcher,obj,libgcc,'-L'+str(sdk/'lib'),'-lc',libgcc],
            output/(name+'-link.log'))
        profile=copy.deepcopy(record)
        command=profile['command']
        command[command.index('--harddrive')+1]=str(directory/'drive-c')
        command[command.index('--disk-a')+1]=str(directory/'documents.st')
        profile.update(kind='magic-scrolling-comparison',viewer=name,
            background_counter=False,original_mgview_sha256=sha256(original),
            document_sha256=sha256(ported/'drive-c/STORY.TXT'),
            scrolling_observer='none' if name=='mgview' else 'startup-only; disabled during scrolling')
        profile['inputs'][str(Path(__file__).resolve().relative_to(ROOT))]=sha256(Path(__file__))
        profile['inputs']['tools/test_magic_scroll.py']=sha256(ROOT/'tools/test_magic_scroll.py')
        profile['binaries']['drive-c/GEMSYS/GEMDESK/MAGXDESK.APP']=sha256(launcher)
        profile['binaries']['drive-c/TEXT.PRG']=sha256(directory/'drive-c/TEXT.PRG')
        profile['documents'].update(path=str(directory/'documents.st'),
            sha256=sha256(directory/'documents.st'))
        (directory/'build.json').write_text(json.dumps(profile,indent=2)+'\n')
        profiles[name]=profile
        script=output/('launch-'+name+'.command')
        script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,
            str(Path(__file__).resolve()),'--output',str(output),'--launch',name])+' "$@"\n')
        script.chmod(0o755)
    (output/'build.json').write_text(json.dumps(dict(profiles=profiles,
        original_binary={'source':str(original),'sha256':sha256(original)}),indent=2)+'\n')
    (output/'README.txt').write_text(
        'MagiC scrolling comparison\n\n'
        'launch-mgview.command starts the original bundled MGVIEW.APP.\n'
        'launch-ported.command starts our original Text Viewer port.\n'
        'Each opens the identical 901-line A:\\STORY.TXT on the same pinned\n'
        'MagiC/68000 8 MHz, 4 MiB ST monochrome setup. Boot/loading fast-forwards;\n'
        'normal speed resumes before comparison. Neither session starts Counter.\n\n'
        'Our viewer logs startup only; scrolling performs no observer file I/O.\n'
        'Use Up/Down in either program. MGVIEW pages with Shift-Up/Shift-Down;\n'
        'our viewer pages with Space/Shift-Space. Click scroll arrows/track\n'
        'for mouse scrolling. Quit MGVIEW with Ctrl+Q; our viewer with Q.\n'
        'Cmd+Q quits Hatari on macOS, AltGr+Q elsewhere. F12 opens settings.\n\n'
        'MGVIEW uses its unchanged 8x16 default font and original window size.\n'
        'Our viewer retains 8x8 text and its original geometry. This allows\n'
        'visual comparison; it is not a normalized performance benchmark.\n'
        'Run one session at a time when assessing responsiveness.\n\n'
        'mgview/documents.st contains the unmodified original MGVIEW.APP and\n'
        'the text fixtures on a read-only FAT12 disk. The launcher also needs\n'
        'the accompanying private MagiC host drive and pinned EmuTOS ROM.\n'
        'This floppy is not a standalone boot image. Build hashes and original\n'
        'release provenance are in build.json. Exec/OF816 images are unchanged.\n')
    return profiles


def ready(output,name):
    if name=='ported':
        lines=reports(output).splitlines()
        return lines and 'loads=1' in lines[-1] and 'dirty=0' in lines[-1]
    path=output/'drive-c/LAUNCH.LOG'
    return path.exists() and 'ready viewer=' in path.read_text()


def launch(output,name):
    directory=output/name
    profile=json.loads((directory/'build.json').read_text())
    with controlled(directory,profile,'interactive-hatari.log') as (process,control):
        wait_for(process,lambda:ready(directory,name),name+' document loading',timeout=40)
        control.sendall(b'hatari-option --fast-forward false\n')
        print(name+' is ready at normal speed. Up/Down scroll; Cmd+Q quits Hatari.',flush=True)
        process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/magic-scroll-comparison')
    parser.add_argument('--cache',type=Path,default=ROOT/'build/atari-st-reference')
    parser.add_argument('--hatari',default='hatari')
    parser.add_argument('--rom')
    parser.add_argument('--offline',action='store_true')
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--launch',choices=('mgview','ported'))
    action.add_argument('--run',action='store_true',help='Build and check both scrolling sessions')
    args=parser.parse_args()
    if args.launch: return launch(args.output.resolve(),args.launch)
    if any(c.isspace() for c in str(args.output.resolve())):
        parser.error('Use an output path without whitespace for Hatari debugger commands')
    profiles=prepare(args)
    if args.run:
        from test_magic_scroll import capture
        capture(args.output.resolve(),profiles)
    print('Original: '+str(args.output/'launch-mgview.command'))
    print('Our viewer: '+str(args.output/'launch-ported.command'))


if __name__=='__main__':
    main()
