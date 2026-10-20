#!/usr/bin/env python3
"""Edit, compile and run BASIC through physical keys in the extracted demo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from build_fastbasic import profile
from console_model import read_cells
from native_program import ROOT, require, sha256
from sdfs_reference import extract
from shell_session_walkthrough import Sessions
from test_demo import run
from test_shell_core import KEYS

KEYS.update({'(':('9',True),')':('0',True),'$':('4',True)})


class Programming(Sessions):
    def failure(self, text, error):
        print('Compiler failure:',text,flush=True)
        s=self.s
        before=s.begin(text);s.ready(before)
        self.failed_result(error)
        self.screen(text)
        self.commands.append(dict(command=text,primary=20,error=error))

    def failed_result(self, error):
        s=self.s
        actual=tuple(int.from_bytes(s.far(s.saved['shell']+offset,4),'little',signed=True)
                     for offset in (32,36))
        require(actual==(20,error),f'BASIC failure result: {actual}')

    def exercise(self, s):
        self.out.mkdir(parents=True,exist_ok=True)
        self.prepare(s)
        self.command('CD WORK:')
        before=s.begin('EDX HELLO.BAS')

        def pending():
            s.rendezvous(f'db(${s.saved["top"]+s.console["INSTANCE_READREADY"]:x})=2')
            s.frames(10)

        def key(name, ctrl=False, shift=False):
            if ctrl:s.b._cmd_ok('KEY CTRL down')
            if shift:s.b._cmd_ok('KEY SHIFT down')
            require(s.b._cmd_ok(f'KEY {name} down')['raw_scan'], 'Physical key required')
            s.frames(4)
            s.b._cmd_ok(f'KEY {name} up')
            if shift:s.b._cmd_ok('KEY SHIFT up')
            if ctrl:s.b._cmd_ok('KEY CTRL up')
            s.frames(4)

        s.rendezvous(f'(db(${s.saved["top"]+s.console["INSTANCE_CAPS"]:x})&$e0)=$e0')
        pending()
        require(b'HELLO BASIC' in bytes(v&127 for v in read_cells(s.far,s.saved['top'])),
                'EDX did not open the BASIC source')
        key('Z',ctrl=True);pending()
        key('BACKSPACE');pending()
        key('X');pending()
        key('2',shift=True);pending()
        key('S',ctrl=True);pending()
        key('RETURN');pending()
        key('ESC');s.ready(before);s.result()
        self.command('FBCI HELLO.BAS HELLO.COM', b'Compiled HELLO.COM')
        self.command('HELLO', b'HELLO BASICX')
        self.command('HELLO.COM', b'42')

        # The argument-free compiler uses inherited cooked input too.
        before=s.begin('FBCI');pending()
        for char in 'HELLO.BAS\n':s.press(char)
        pending()
        for char in 'SECOND.COM\n':s.press(char)
        s.ready(before);s.result()
        self.command('SECOND', b'HELLO BASICX')

        self.command('FBCI INPUT.BAS INPUT.COM', b'Compiled INPUT.COM')
        before=s.begin('INPUT');pending()
        for char in 'ADA\n':s.press(char)
        pending()
        require(b'HELLO ADA' in read_cells(s.far,s.saved['top']), 'Cooked INPUT failed')
        s.press('K');s.ready(before);s.result()
        require(b'KEY 75' in self.screen('single-key'), 'GET did not return the physical key')
        require(s.number(s.saved['top']+s.console['INSTANCE_CAPS'],1)&0xe0==0,
                'BASIC left console modes active')

        self.failure('FBCI MISSING.BAS BAD.COM',205)
        self.command('ECHO IF >BAD.BAS')
        self.failure('FBCI BAD.BAS BAD.COM',306)
        self.failure('FBCI HELLO.BAS SYS:FAIL.COM',214)
        self.command('SECOND', b'HELLO BASICX')
        self.command('ECHO "REPEAT : UNTIL KEY() : GET K : ? K" >KEY.BAS')
        self.command('FBCI KEY.BAS KEY.COM')
        before=s.begin('KEY')
        s.rendezvous(f'(db(${s.saved["top"]+s.console["INSTANCE_CAPS"]:x})&$40)=$40')
        s.frames(20);s.press('Q');s.ready(before);s.result()
        require(b'81' in self.screen('poll-key'), 'KEY/GET did not share the queued key')
        self.command('ECHO >EMPTY.BAS')
        self.command('FBCI EMPTY.BAS EMPTY.COM')
        self.command('EMPTY')
        self.command('ECHO "DIM A(30000)" >NOMEM.BAS')
        self.command('FBCI NOMEM.BAS NOMEM.COM')
        self.failure('NOMEM',103)
        self.command('ECHO "GRAPHICS 0" >BAD.BAS')
        self.failure('FBCI BAD.BAS BAD.COM',306)
        self.command('ECHO "GET K : ? K : INPUT S$ : ? S$" >READ.BAS')
        self.command('FBCI READ.BAS READ.COM')
        self.command('ECHO ADA >NAME.TXT')
        self.command('READ <NAME.TXT >RESULT.TXT')
        self.command('TYPE RESULT.TXT',b'65')
        self.command('FBCI BUSY.BAS BUSY.COM')
        before=s.begin('BUSY')
        s.rendezvous(f'(db(${s.saved["top"]+s.console["INSTANCE_CAPS"]:x})&$40)=$40')
        s.frames(15);s.press('\x03');s.ready(before);self.failed_result(304)
        self.command('ARC',b'filename is given.')
        self.command('ECHO abc >ABC.TXT')
        self.command('MD5 ABC.TXT',b'MD5 (ABC.TXT)')
        self.command('C:HELLO',b'Hello from disk!')
        s.saved['integration']=dict(fastbasic=True,physical_input_get_key=True,
                                    busy_break=True,commands=self.commands)
        s.save_screen(self.bundle/'boot-smoke.png')
        shutil.copyfile(self.bundle/'boot-smoke.png',self.bundle/'fastbasic.png')
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def check(bundle):
    distribution=bundle/'extracted'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        checks=archive.read('exec816-demo/SHA256SUMS').decode().splitlines()
        names={'exec816-demo/SHA256SUMS'}
        for line in checks:
            digest,name=line.split('  ',1)
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                    'Invalid distribution member')
            member='exec816-demo/'+name
            require(hashlib.sha256(archive.read(member)).hexdigest()==digest,
                    'Changed distribution member: '+name)
            names.add(member)
        require(names==set(archive.namelist()),'Incomplete distribution checksums')
        if distribution.exists():shutil.rmtree(distribution)
        archive.extractall(distribution)
    root=distribution/'exec816-demo'
    result=run(bundle,boot_smoke=True,distribution_root=root,
               integration=Programming(bundle/'programming',bundle))
    readback=bundle/'readback'
    extract(bundle/'work-walkthrough.atr',readback)
    require((readback/'HELLO.BAS').read_bytes()==b'? "HELLO BASICX"\x9b? 6*7\x9b',
            'Editor save readback differs')
    result['generated']={name:dict(sha256=sha256(readback/name),
                                 profile=profile((readback/name).read_bytes()))
                         for name in ('HELLO.COM','SECOND.COM','INPUT.COM','BUSY.COM')}
    (bundle/'fastbasic-checks.json').write_text(json.dumps(
        dict(status='pass',tier='development',result=result),indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    check(args.bundle.resolve())
    print('Packaged FastBasic edit/compile/run checks passed')
