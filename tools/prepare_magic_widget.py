#!/usr/bin/env python3
"""Prepare the shared GEM Widget and Counter pair on pinned MagiC/Hatari."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile

from prepare_st_reference import ROOT,ADAPTER,run,sha256
from prepare_magic_counters import prepare as prepare_reference
from prepare_magic_text import wait_for

CASES=('solo','silent','paint')


def prepare(args):
    record=prepare_reference(args)
    out=args.output.resolve();sdk=args.cache.resolve()/'sdk'
    objects,drive=out/'objects',out/'drive-c'
    cc,ld=sdk/'bin/m68k-atari-tos-gnu-gcc',sdk/'bin/m68k-atari-tos-gnu-ld'
    sources=dict(widget=ROOT/'examples/gem-widget/widget.c',
        widget_main=ROOT/'examples/gem-widget/main.c',
        pulse_main=ROOT/'examples/gem-widget/counter-main.c',
        widget_observe=ADAPTER/'widget-observe.c',pulse_observe=ADAPTER/'widget-observe.c',
        widget_launcher=ADAPTER/'widget-launcher.c')
    for name,source in sources.items():
        run([cc,'-O2','-Wall','-ffunction-sections','-fdata-sections','-MMD',
            *(['-DSAMPLE_WIDGET'] if name=='widget_observe' else []),
            '-I'+str(ADAPTER/'include'),'-I'+str(ROOT/'c/include'),'-I'+str(ROOT),
            '-c',source,'-o',objects/(name+'.o')],objects/(name+'.log'))
    libgcc=Path(run(['m68k-elf-gcc','-m68000','-print-libgcc-file-name']))
    libraries=[libgcc,'-L'+str(sdk/'lib'),'-lc',libgcc]
    for target,names in [('WIDGET',('widget_main','widget','widget_observe')),
                         ('PULSE',('pulse_main','counter','pulse_observe'))]:
        run([ld,'--gc-sections','--wrap=evnt_multi','--wrap=main','-o',drive/(target+'.PRG'),
            *(objects/(name+'.o') for name in (*names,'bindings')),*libraries],
            objects/(target.lower()+'-link.log'))
    launcher=drive/'GEMSYS/GEMDESK/MAGXDESK.APP'
    run([ld,'-o',launcher,objects/'widget_launcher.o',*libraries],objects/'launcher-link.log')
    shutil.copyfile(out/'inputs/MAGIC.A/EXTRAS/KEYTABS/US/KEYTABLS.SYS',drive/'USKEYS.SYS')
    (drive/'CASE.TXT').write_text('paint\n')
    for mode in CASES:
        path=out/('launch-'+mode+'.command')
        path.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,str(Path(__file__).resolve()),
            '--output',str(out),'--launch',mode])+' "$@"\n')
        path.chmod(0o755)
    # The old two-Counter launcher has been replaced in this private profile.
    (out/'launch-hatari.command').unlink(missing_ok=True)
    inputs={Path(__file__).resolve(),ROOT/'tools/test_magic_widget.py',ROOT/'tools/widget_model.py',ROOT/'tools/widget_observe.py',*sources.values(),
        ROOT/'examples/gem-widget/widget.h'}
    for name in sources:
        dependencies=(objects/(name+'.d')).read_text().replace('\\\n','').split(':',1)[1]
        inputs.update(Path(p) for p in dependencies.split())
    record['inputs'].update({str(p.relative_to(ROOT)):sha256(p) for p in sorted(inputs)})
    record.update(kind='magic-shared-widget',cases=CASES,
        shared_sources=['examples/gem-widget/widget.c','examples/gem-widget/main.c',
                        'examples/gem-widget/counter-main.c','examples/gem-counter/counter.c'],
        observation='startup addresses and exit only; no periodic guest file I/O',
        counter_period_ms=100,widget_work=[32,56,304,128])
    record['binaries']={str(p.relative_to(out)):sha256(p) for p in
        (drive/'WIDGET.PRG',drive/'PULSE.PRG',launcher,drive/'MAGIC.RAM',drive/'AUTO/MAGXBOOT.PRG')}
    record['toolchain_artifacts']={str(p):sha256(p) for p in (cc,ld,sdk/'lib/libc.a',libgcc)}
    (out/'README.txt').write_text(
        'Shared GEM Widget + Counter on MagiC\n\n'
        'launch-solo.command: Widget alone\n'
        'launch-silent.command: Widget + 100 ms Counter without timer drawing\n'
        'launch-paint.command: Widget + 100 ms Counter with timer drawing\n\n'
        'Click Toggle or press Space to change the button and label. Q or the\n'
        'closer exits Widget. Counter keeps running until its own closer.\n'
        'Drag either window to overlap/expose the other. Silent Counter repairs\n'
        'exposure but does not repaint on ticks. It counts delivered timer events,\n'
        'not wall-clock deadlines. Close Hatari before starting another case.\n'
        'Boot fast-forwards; interaction resumes at normal speed. Cmd+Q quits\n'
        'Hatari on macOS; AltGr+Q elsewhere. F12 opens Hatari settings.\n\n'
        'Application bodies and startup mains are shared with Exec. The ST\n'
        'uses its native AES object font and an 8x8 VDI Counter font. This is a\n'
        'functional comparison harness; no latency or relative-speed claim.\n'
        'No guest diagnostic file writes occur between startup and exit.\n')
    (out/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def descriptors(out,name):
    path=out/'drive-c'/(name.upper()+'.LOG')
    if not path.exists():return {}
    line=path.read_text().splitlines()
    if not line or not line[0].startswith('id='):return {}
    decimal={'id','window','period','silent'}
    return {key:int(value,10 if key in decimal else 16)
            for key,value in (field.split('=') for field in line[0].split())}


@contextmanager
def controlled(out,record,mode,log_name='interactive-hatari.log'):
    if mode not in CASES:raise ValueError('Unknown Widget case')
    for name in ('WIDGET.LOG','PULSE.LOG','LAUNCH.LOG'):
        (out/'drive-c'/name).unlink(missing_ok=True)
    (out/'drive-c/CASE.TXT').write_text(mode+'\n')
    with tempfile.TemporaryDirectory(prefix='exec816-widget-',dir='/tmp') as temporary:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
            address=str(Path(temporary)/'control.sock')
            server.bind(address);server.listen(1);server.settimeout(10)
            with (out/log_name).open('w') as log:
                process=subprocess.Popen([*record['command'],'--fast-forward','true',
                    '--control-socket',address],stdout=log,stderr=subprocess.STDOUT)
                try:
                    control,_=server.accept()
                    with control:yield process,control
                finally:
                    if process.poll() is None:
                        process.terminate();process.wait(timeout=10)


def launch(out,record,mode):
    with controlled(out,record,mode) as (process,control):
        wait_for(process,lambda:descriptors(out,'widget') and
            (mode=='solo' or descriptors(out,'pulse')),'Widget startup',timeout=40)
        control.sendall(b'hatari-option --fast-forward false\n')
        print(mode+': Widget ready at normal speed. Space toggles; Q closes Widget.',flush=True)
        process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/magic-widget')
    parser.add_argument('--cache',type=Path,default=ROOT/'build/atari-st-reference')
    parser.add_argument('--hatari',default='hatari');parser.add_argument('--rom')
    parser.add_argument('--offline',action='store_true')
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--launch',choices=CASES)
    action.add_argument('--run',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if any(c.isspace() for c in str(out)):parser.error('Use an output path without whitespace')
    if args.launch:return launch(out,json.loads((out/'build.json').read_text()),args.launch)
    record=prepare(args)
    if args.run:
        from test_magic_widget import capture
        capture(out,record)
    print('Launch: '+str(out/'launch-paint.command'))


if __name__=='__main__':main()
