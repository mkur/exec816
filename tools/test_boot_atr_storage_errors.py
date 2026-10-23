#!/usr/bin/env python3
"""Focused native-entry replays for disk-full and real FujiNet read-only media."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from build_bootable_atr import build
from filesystem_audit import Audit
from fujinet_pc_peer import FujiNetPC
from native_program import require,sha256
from sdfs_reference import extract
from test_bootable_atr import DiskBoot
from test_demo import run


class Failure:
    interrupt_marker='native_nmi'
    def __init__(self,kind):self.kind=kind
    def exercise(self,s):
        s.saved.setdefault('desktop_menu',{})
        from desktop_menu_check import Menus
        from desktop_mouse import schedule
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            position=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            position=schedule(s.b,s.p,position,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(12)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(30)
        Menus(s,click,move).select('Shell')
        s.command('ASSIGN',b'WORK: -> D1:WORK')
        s.command('HELLO',b'Hello from disk!')
        previous=s.begin('ECHO blocked >WORK:REJECT.TXT');s.ready(previous)
        cause=int.from_bytes(s.far(s.saved['shell']+36,4),'little',signed=True)
        require(cause==221 if self.kind=='full' else cause in (3,214,223),
                f'{self.kind}: unexpected save failure {cause}')
        s.result(cause);self.error=cause
        s.command('ECHO console-alive',b'console-alive')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for ch in 'EXIT':s.press(ch)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def check(bundle,output,snapshot,kind,firmware=None):
    output.mkdir(parents=True,exist_ok=True)
    image=output/'exec816.atr'
    shutil.copyfile(bundle/'of816/exec816.atr',image)
    if kind=='full':
        audit=Audit(image.read_bytes());free=audit.sdfs()['free']
        sectors=next(n for n in range(free-100,free) if n+(n+125)//126==free)
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'source';extract(image,source)
            (source/'WORK/FILL.BIN').write_bytes(bytes(sectors*256))
            build(image,source,bundle/'of816/Exec-of816.xex',output/'reader')
        audit=Audit(image.read_bytes());require(audit.sdfs()['free']==0,'Disk-full fixture has space')
    original=sha256(image)
    boot=DiskBoot(bundle,native_snapshot=snapshot)
    failure=Failure(kind)
    if kind=='readonly':
        require(firmware is not None,'Read-only transport case requires FujiNet-PC')
        with FujiNetPC(output/'peer',image,firmware,readonly=True) as peer:
            result=run(bundle,boot_smoke=True,bootstrap=boot,media_path=image,integration=failure,
                       sio_peer=peer,emulator_output=output/'emulator')
            require(not peer.error,'FujiNet protocol failed')
        require(sha256(image)==original,'Read-only peripheral modified the ATR')
    else:
        result=run(bundle,boot_smoke=True,bootstrap=boot,media_path=image,integration=failure,
                   emulator_output=output/'emulator')
    audit=Audit(image.read_bytes());allocation=audit.sdfs()
    require(not audit.files.get('WORK/REJECT.TXT'), 'Failed save persisted data')
    result.update(status='pass',tier='development',qualification=False,case=kind,
                  native_entry_replay=boot.report,error=failure.error,allocation=allocation)
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(kind,'save failure passed',failure.error,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--case',choices=('full','readonly'),required=True);p.add_argument('--fujinet-pc',type=Path)
    a=p.parse_args();check(a.bundle.resolve(),a.output.resolve(),a.snapshot.resolve(),a.case,a.fujinet_pc)
