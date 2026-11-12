#!/usr/bin/env python3
"""Build and launch the original Exec text viewer as an ordinary MagiC app."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from prepare_st_reference import ROOT, ADAPTER, run, sha256
from prepare_magic_counters import prepare as prepare_counters


def prepare(args):
    for command in ('mformat','mcopy'):
        if not shutil.which(command):
            raise RuntimeError('Missing '+command+'; install mtools (brew install mtools)')
    # Reuse the pinned SDK, ROM, release installation and Counter build.
    record = prepare_counters(args)
    output, sdk = args.output.resolve(), args.cache.resolve()/'sdk'
    objects, drive = output/'objects', output/'drive-c'
    cc, ld = sdk/'bin/m68k-atari-tos-gnu-gcc', sdk/'bin/m68k-atari-tos-gnu-ld'
    sources = {name: ROOT/'examples/gem-text'/f'{name}.c' for name in ('text','document')}
    sources.update(platform=ADAPTER/'text-platform.c', text_main=ADAPTER/'text-main.c',
        text_launcher=ADAPTER/'text-launcher.c')
    path_source=ROOT/'c/calypsi/file-list.c'
    functions=[]
    body=path_source.read_text()
    for name in ('FileJoin','FileSplit'):
        match=re.search(r'^WORD '+name+r'\([^\n]*\)\n\{',body,re.M)
        if not match: raise ValueError('Missing shared path helper: '+name)
        functions.append(body[match.start():body.index('\n}',match.end())+2])
    helpers=objects/'path-helpers.c'
    helpers.write_text('#include "c/calypsi/file-list.h"\n#include <string.h>\n'+
        '\n\n'.join(functions)+'\n')
    sources['path_helpers']=helpers
    for name, source in sources.items():
        run([cc, '-O2', '-Wall', '-ffunction-sections', '-fdata-sections', '-MMD',
            '-I'+str(ADAPTER/'include'), '-I'+str(ROOT/'c/include'), '-I'+str(ROOT),
            '-c', source, '-o', objects/(name+'.o')], objects/(name+'.log'))
    libgcc = run(['m68k-elf-gcc','-m68000','-print-libgcc-file-name'])
    libraries = [libgcc,'-L'+str(sdk/'lib'),'-lc',libgcc]
    wrappers = ('evnt_multi','wind_update','wind_set','v_opnvwk','menu_bar',
        'fsel_exinput','appl_exit')
    run([ld,'--gc-sections','-o',drive/'TEXT.PRG',
        *('--wrap='+name for name in wrappers),
        *(objects/(name+'.o') for name in ('text_main','text','document','platform','path_helpers','bindings')),
        *libraries],objects/'text-link.log')
    run([cc,'-O2','-Wall','-DREFERENCE_COUNTER_SECOND_Y=288',
        '-I'+str(ADAPTER/'include'),'-I'+str(ROOT/'c/include'),'-I'+str(ROOT),
        '-c',ADAPTER/'counter-main.c','-o',objects/'counter-main.o'],objects/'counter-main.log')
    run([ld,'-o',drive/'COUNTER.PRG','--wrap=evnt_multi',objects/'counter-main.o',
        objects/'counter.o',objects/'bindings.o',*libraries],objects/'counter-link.log')
    run([ld,'-o',drive/'GEMSYS/GEMDESK/MAGXDESK.APP',objects/'text_launcher.o',*libraries],
        objects/'launcher-link.log')
    (drive/'STORY.TXT').write_bytes(('MagiC text viewer: original Exec application\r\n'+
        ''.join(f'Line {i:04d}: shared viewer, GEM events and ordinary file reads.\r\n'
            for i in range(1,901))).encode('ascii'))
    (drive/'VIEW.TXT').write_bytes((ROOT/'examples/gem-text/VIEW.TXT').read_bytes())
    (drive/'SMALL.TXT').write_bytes(b'A second document\r\nTabs\tuse eight columns.\r\n')
    (drive/'BIG.TXT').write_bytes(b'X'*65537)
    keymap=output/'inputs/MAGIC.A/EXTRAS/KEYTABS/US/KEYTABLS.SYS'
    shutil.copyfile(keymap,drive/'USKEYS.SYS')
    # MagiC's built-in selector uses its native filesystem internally. Hatari's
    # host-folder interception cannot supply those internal directory calls.
    # Keep programs/logs on host C:, and documents on a real FAT12 floppy A:.
    disk=output/'documents.st'
    run(['mformat','-i',disk,'-C','-f','720','-v','TEXTDEMO','::'],objects/'mformat.log')
    for name in ('STORY.TXT','VIEW.TXT','SMALL.TXT','BIG.TXT'):
        run(['mcopy','-i',disk,drive/name,'::'+name],objects/('mcopy-'+name+'.log'))
    record['command']+=['--disk-a',str(disk),'--drive-b','false','--protect-floppy','on']
    inputs={Path(__file__).resolve(),ROOT/'tools/test_magic_text.py',*sources.values(),
         ROOT/'examples/gem-text/text.h',
         ROOT/'examples/gem-text/document.h',ROOT/'examples/gem-text/VIEW.TXT',path_source,
         ADAPTER/'include/string.h'}
    for name in sources:
        dependencies=(objects/(name+'.d')).read_text().replace('\\\n','').split(':',1)[1]
        inputs.update(Path(path) for path in dependencies.split())
    record['inputs'].update({str(p.relative_to(ROOT)):sha256(p) for p in sorted(inputs)})
    record.update(kind='magic-original-text-viewer',counter_second_y=288,
        shared_sources=['examples/gem-text/text.c','examples/gem-text/document.c'])
    record['binaries']={str(p.relative_to(output)):sha256(p) for p in
        (drive/'TEXT.PRG',drive/'COUNTER.PRG',drive/'GEMSYS/GEMDESK/MAGXDESK.APP',
         drive/'MAGIC.RAM',drive/'AUTO/MAGXBOOT.PRG')}
    record['documents']={'path':str(disk),'sha256':sha256(disk),'filesystem':'FAT12',
        'drive':'A','access':'readonly','mformat':run(['mformat','-V']).splitlines()[0]}
    record['keyboard']={'source':str(keymap),'sha256':sha256(keymap),
        'primary_table_bytes':384,'owner':'resident desktop launcher'}
    record['toolchain_artifacts']={str(p):sha256(p) for p in
        (cc,ld,sdk/'lib/libc.a',Path(libgcc))}
    script=output/'launch-hatari.command'
    script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,str(Path(__file__).resolve()),
        '--output',str(output),'--launch'])+' "$@"\n')
    script.chmod(0o755)
    (output/'README.txt').write_text(
        'Original text viewer on MagiC\n\n'
        'Run launch-hatari.command. Boot/loading fast-forwards, then normal\n'
        'speed resumes with STORY.TXT and an independent Counter visible.\n'
        'Space pages down, Shift-Space pages up, Up/Down scroll one line.\n'
        'O opens MagiC\'s native file selector on A:. Undo cancels the selector;\n'
        'Escape clears its filename field. Return accepts the selected name.\n'
        'Escape in the viewer cancels a pending load. Q or the closer exits.\n'
        'Cmd+Q quits Hatari on macOS; AltGr+Q elsewhere. F12 opens settings.\n\n'
        'documents.st is a read-only native FAT12 floppy in A:. SYS: maps to A:.\n'
        'STORY.TXT is long; SMALL.TXT is short; BIG.TXT exceeds the 64 KiB limit.\n'
        'Host C: supplies applications/logs, not the native file selector.\n'
        'Close this setup before opening another instance of its launcher.\n\n'
        'The original text.c/document.c sources are compiled unchanged. This\n'
        'first reference retains their 640x240 window-sizing assumptions;\n'
        'full-height ST resize/drag behavior is not supported by this slice.\n'
        'The viewer retains four-row paint bands and 1 KiB loading steps.\n'
        'This reference is separate from the OF816/Exec demo and makes no\n'
        'performance, disk-throughput or physical ST qualification claim.\n')
    (output/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def reports(output):
    path=output/'drive-c/TEXT.LOG'
    return path.read_text() if path.exists() else ''


def wait_for(process,predicate,description,timeout=20):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError('Hatari exited while waiting for '+description)
        value=predicate()
        if value: return value
        time.sleep(.05)
    raise RuntimeError('Timed out waiting for '+description)


@contextmanager
def controlled(output,record,name):
    for filename in ('TEXT.LOG','LAUNCH.LOG','COUNT2.LOG'):
        (output/'drive-c'/filename).unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='exec816-text-',dir='/tmp') as temporary:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
            address=str(Path(temporary)/'control.sock')
            server.bind(address);server.listen(1);server.settimeout(10)
            with (output/name).open('w') as log:
                process=subprocess.Popen([*record['command'],'--fast-forward','true',
                    '--control-socket',address],stdout=log,stderr=subprocess.STDOUT)
                try:
                    control,_=server.accept()
                    with control:
                        yield process,control
                finally:
                    if process.poll() is None:
                        process.terminate();process.wait(timeout=10)


def launch(output,record):
    with controlled(output,record,'interactive-hatari.log') as (process,control):
        def loaded():
            lines=reports(output).splitlines()
            return lines and 'dirty=0' in lines[-1] and 'loads=1' in lines[-1]
        wait_for(process,loaded,'the first document')
        control.sendall(b'hatari-option --fast-forward false\n')
        print('Text viewer and Counter are running. Cmd+Q quits Hatari on macOS.',flush=True)
        process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/magic-text-viewer')
    parser.add_argument('--cache',type=Path,default=ROOT/'build/atari-st-reference')
    parser.add_argument('--hatari',default='hatari')
    parser.add_argument('--rom')
    parser.add_argument('--offline',action='store_true')
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--launch',action='store_true',help='Launch an already prepared demo')
    action.add_argument('--run',action='store_true',help='Build and run focused MagiC checks')
    args=parser.parse_args()
    if any(c.isspace() for c in str(args.output.resolve())):
        parser.error('Hatari debugger paths require an output path without whitespace')
    if args.launch:
        record=json.loads((args.output/'build.json').read_text())
        launch(args.output.resolve(),record)
        return 0
    record=prepare(args)
    if args.run:
        from test_magic_text import capture
        capture(args.output.resolve(),record)
    print(f'Launch: {args.output}/launch-hatari.command')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
