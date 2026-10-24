#!/usr/bin/env python3
"""Packaged parked BASIC, real tools, busy Run during EDX, and resumed state."""
import argparse
import json
from pathlib import Path

from basic_build_model import FIELDS as JOB,RESIDENT_FIELDS
from gem_applications import instances
from generate_console import constants
from native_program import require,sha256
from test_fastbasic_session_demo import PersistentInterpreter
from test_twelve_task_demo import check


class ResidentGuest(PersistentInterpreter):
    def source_checks(self,**c):
        super().source_checks(**c)
        n,job=c['n'],c['job'];menus=c['menus'];key=c['key'];reach=c['reach']
        menus.select('FastBasic');key('K',ctrl=True)
        reach('dw($%x)=0'%job)
        require(n(job+JOB['cause'],4)==304,'Stop the live INPUT before parking')
        app=next(v for v in instances(self.s.b,self.s.p,self.bundle/'bitmap-console') if v['name']=='basic')
        resident=app['symbols']['resident']
        def identity():
            return tuple(n(resident+RESIDENT_FIELDS[name],4) for name in ('image','child'))
        held=identity();require(all(held),'Missing parked interpreter')
        menus.select('Shell')
        self.command('MD5 ABC.TXT',b'MD5')
        self.command('ARC',b'filename is given.')
        self.command('FBCI WORK:HELLO.BAS RAM:PARK.COM',b'Compiled')
        self.command('RAM:PARK.COM',b'42')
        require(identity()==held,'Tools replaced the parked interpreter')
        before=self.s.begin('EDX EDIT.TXT');a=constants();top=self.s.saved['top']
        ready=top+a['INSTANCE_READREADY'];caps=top+a['INSTANCE_CAPS']
        reach('(db($%x)=2)&((db($%x)&224)=224)'%(ready,caps))
        abi=json.loads((Path(__file__).resolve().parents[1]/'abi/sdx.json').read_text())['runtime']
        owner=n(abi['state']['lease'],2);require(owner in (1,2),'EDX has no lease')
        context=abi['context_base']+(owner-1)*abi['context_bytes']
        stack=n(context+abi['fields']['guest_s'],2)
        frame=self.s.b.memdump(stack+1,13)
        menus.select('FastBasic');c['replace']('A=999')
        previous=n(job+JOB['job'],4);key('RETURN',ctrl=True)
        reach('(dw($%x)=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],previous))
        require(n(job+JOB['cause'],4)==202,'Busy Run must report object in use')
        require(self.s.b.memdump(stack+1,13)==frame,'Busy Run altered EDX frame')
        menus.select('Shell');key('BREAK');self.s.ready(before)
        primary,secondary=(int.from_bytes(self.s.far(self.s.saved['shell']+off,4),'little',signed=True) for off in (32,36))
        require((primary,secondary)==(20,304),'EDX cancellation result')
        menus.select('FastBasic');c['replace']('PRINT "PARK";A')
        previous=n(job+JOB['job'],4);key('RETURN',ctrl=True)
        reach('(dw($%x)=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],previous))
        require(n(job+JOB['cause'],4)==0 and b'PARK3' in c['output'](),'Busy Run changed BASIC state')
        require(identity()==held,'BASIC reloaded after tools')
        self.s.saved['resident_stack']=dict(tools=True,edx_wait=True,busy_run=True,frame_intact=True,state_retained=True)
        # Continue the existing live-input Quit/resource-collection walkthrough.
        c['replace']('INPUT Z');key('RETURN',ctrl=True)
        menus.select('FastBasic output')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--native-snapshot',type=Path)
    args=parser.parse_args();bundle=args.bundle.resolve();bootstrap=None
    if args.native_snapshot:
        from test_bootable_atr import DiskBoot
        bootstrap=DiskBoot(bundle,native_snapshot=args.native_snapshot.resolve())
    result=check(bundle,ResidentGuest,bootstrap)
    result['runner_sha256']=sha256(Path(__file__))
    (bundle/'resident-demo-results.json').write_text(json.dumps(result,indent=2)+'\n')
