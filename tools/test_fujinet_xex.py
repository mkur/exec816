#!/usr/bin/env python3
"""Cold-boot an extracted split package through real FujiNet PicoBoot/XEX."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import zipfile

from native_program import ROOT,require,sha256
from fujinet_pc_peer import FujiNetPC
from test_demo import run
from test_bootable_atr import wait_at,DiskBoot
from test_of816 import check_loading_paused,check_loading_complete,check_boot_guards
from filesystem_audit import Audit


def option_boot(b,target,failures=(),timeout=180,condition=None):
    # CONFIG restarts the ROM without an emulator cold reset. Keep OPTION
    # asserted until its BASIC decision and the first XEX transfer complete.
    b._cmd_ok('CONSOL option')
    try:wait_at(b,target,failures,timeout,condition=condition)
    finally:b._cmd_ok('CONSOL')


class XexBoot:
    def __init__(self,bundle,output,menu=False,manual=False):
        self.bundle,self.output=bundle,output
        self.monitor=json.loads((bundle/'of816/of816.json').read_text())
        self.report={}
        self.menu=menu
        self.manual=manual

    def __call__(self,b,p):
        try:self.boot(b,p)
        except Exception:
            b.pause();b.state_save(str(self.output/'failure.altstate2'))
            labels=self.monitor.get('boot_sio',{}).get('labels',{})
            (self.output/'failure.json').write_text(json.dumps(dict(regs=b.regs(),
                state={k:b.memdump(v,4).hex() for k,v in labels.items() if
                       k.startswith(('bo_','reader_','take_','boot_'))}),indent=2)+'\n')
            raise

    def boot(self,b,p):
        labels=p['labels'];mon=self.monitor;failure=(labels['loader_done'],)
        if mon.get('boot_sio'):
            reader=mon['boot_sio']['labels']
            failure+=(reader['reader_failed'],reader['reader_park'])
        b.cold_reset()
        if self.menu:
            b.resume();deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                # CONFIG's final full-path query completes the eight drive
                # slots. Give its display/input loop time to become idle.
                if (self.peer.commands and self.peer.commands[-1]['device']==0x70 and
                    self.peer.commands[-1]['command']==0xda and self.peer.commands[-1]['aux']==7):
                    time.sleep(1);break
                time.sleep(.1)
            else:raise RuntimeError('FujiNet CONFIG menu did not become ready')
            b.pause();b.state_save(str(self.output/'menu-before-option.altstate2'))
            # CONFIG occupies the future reader arena. Arm boot addresses only
            # after PicoBoot has replaced it with the generated guarded reader.
            condition='dw($4000)=$a5a5' if mon.get('boot_sio') else None
            option_boot(b,labels['loader_init'],failure,condition=condition)
            self.report['configuration_menu_option_boot']=True
            self.report['option_held_through_first_init']=True
        else:wait_at(b,labels['loader_init'],failure,180)
        self.report['first_native_init_frame']=b.eval_expr('@frame')
        self.report.update(rom_disk_boot=True,memlo=b.peek16(0x2e7),memtop=b.peek16(0x2e5))
        wait_at(b,mon['labels']['of_start'],failure,180)
        self.report['of816_frame']=b.eval_expr('@frame')
        settings=check_loading_paused(b,mon,p)
        vectors=b.memdump(0x256,9);iocb=b.memdump(0x340,32)
        serial_vectors=b.memdump(0x20a,6)
        if self.manual:
            from boot_forth_check import exercise
            self.report['manual'],settings=exercise(b,mon,p,self.output/'forth')
        else:
            wait_at(b,mon['labels']['of_autoboot'],failure,30)
            start=b.eval_expr('@frame')
            self.report['countdown_start_frame']=start
            wait_at(b,mon['labels']['of_handoff'],failure,30)
            self.report['countdown_frames']=b.eval_expr('@frame')-start
            require(249<=self.report['countdown_frames']<=251,'Incorrect OF816 countdown')
        self.report['of816_return_frame']=b.eval_expr('@frame')
        check_boot_guards(b,mon['layout'])
        wait_at(b,labels['loader_start'],failure,900)
        check_loading_complete(b,mon,p,settings)
        require(b.memdump(0x256,9)==vectors and b.memdump(0x340,32)==iocb,'Firmware context changed')
        require(b.memdump(0x20a,6)==serial_vectors,'Boot serial vectors survived handoff')
        snapshot=self.output/'before-native.altstate2';b.state_save(str(snapshot))
        verifier=object.__new__(DiskBoot);verifier.report={};verifier.verify_native(p,snapshot)
        self.report.update(verifier.report,loader_error=b.peek(labels['loader_error'])[0],
                           native_handoff_frame=b.eval_expr('@frame'),guards='intact',firmware_context='restored')
        print('FujiNet PicoBoot loaded native image:',self.report,flush=True)
        wait_at(b,labels['start'],(),30);b.bp_clear_all()


class Workspace:
    interrupt_marker='native_nmi'

    def __init__(self,restore=False):self.restore=restore

    def exercise(self,s):
        from desktop_menu_check import Menus
        from desktop_mouse import schedule
        from gem_applications import symbols
        from colour_desktop_model import FIELDS
        s.saved.setdefault('desktop_menu',{})
        directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        sy=symbols(s.b,s.p,directory,'desktop',s.number(resident['GEMDesktopChildren'],4));desk=sy['GEMDesk']
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            position=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            s.saved['pointer']=schedule(s.b,s.p,position,(x,y))
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(12)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(30)
        menus=Menus(s,click,move)
        s.rendezvous('dw($%x)=1'%(desk+FIELDS['ready']))
        if self.restore:require(s.number(desk+FIELDS['settingsLoaded'],2)==1,'Preferences lost after reboot')
        menus.select('Shell')
        mounts=s.command('MOUNT',b'D2:')
        require(b'WORK:' in mounts and b'D1:' not in mounts,'Incorrect split native mounts')
        s.command('ASSIGN',b'D2:C')
        s.command('HELLO',b'Hello from disk!')
        if not self.restore:
            s.command('ECHO "PRINT 42" >WORK:FUJIBOOT.BAS')
            s.command('ECHO split-persisted >WORK:FUJI.TXT')
        s.command('FB WORK:FUJIBOOT.BAS',b'42')
        s.command('CAT WORK:FUJI.TXT',b'split-persisted')
        if not self.restore:
            menus.select('SYS:');click(296,8);click(304,28+5*11);s.frames(120)
            require(not s.number(desk+FIELDS['error'],4),'Save Settings failed')
            menus.select('Shell')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for character in 'EXIT':s.press(character)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def check(bundle,output,firmware,restore=False,menu=False,manual=False):
    output.mkdir(parents=True,exist_ok=True)
    extracted=output/'extracted'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            require(hashlib.sha256(archive.read('exec816-demo/'+name)).hexdigest()==digest,'ZIP checksum mismatch')
        require('exec816-demo/exec816.atr' not in archive.namelist(),'Expected split media')
        archive.extractall(extracted)
    media=output/'media';media.mkdir(exist_ok=True)
    for name in ('Exec-of816.xex','system.atr','work.atr'):
        if name!='work.atr' or not restore:shutil.copyfile(extracted/'exec816-demo'/name,media/name)
    before={name:sha256(media/name) for name in ('Exec-of816.xex','system.atr','work.atr')}
    boot=XexBoot(bundle,output,menu,manual)
    mounts=[(1,media/'Exec-of816.xex',True),(2,media/'system.atr',True),(8,media/'work.atr',False)]
    with FujiNetPC(output/'peer',media/'Exec-of816.xex',firmware,mounts=mounts,configuration_menu=menu) as peer:
        boot.peer=peer
        result=run(bundle,boot_smoke=True,bootstrap=boot,media_path=media/'system.atr',system_drive=2,
                   integration=Workspace(restore),sio_peer=peer,emulator_output=output/'emulator',expected_cache=128 if manual else None)
        require(not peer.error,'FujiNet relay error: '+str(peer.error))
    require(all(sha256(media/name)==before[name] for name in ('Exec-of816.xex','system.atr')),'Read-only boot/system media changed')
    audit=Audit((media/'work.atr').read_bytes());allocation=audit.sdfs()
    require(b'PRINT 42' in audit.files['FUJIBOOT.BAS'] and b'split-persisted' in audit.files['FUJI.TXT'],'Saved bytes missing')
    require(audit.files['DESKTOP.CFG'].startswith(b'EXEC816_DESKTOP 1\n'),'Preferences missing')
    relay=json.loads((output/'peer/relay.json').read_text())
    require(all(any(c['device']==device and c['command']==0x52 for c in relay['commands']) for device in (0x31,0x32,0x38)),
            'Did not exercise all three firmware mounts')
    require(any(c['device']==0x38 and c['command'] in (0x50,0x57) for c in relay['commands']) or restore,'No firmware WORK writes')
    result.update(status='pass',tier='development',qualification=False,xex_boot=boot.report,
                  persisted=restore,media_before=before,work_after=sha256(media/'work.atr'),allocation=allocation,
                  firmware=dict(path=str(firmware),sha256=sha256(firmware),relay=relay))
    (output/('reboot-results.json' if restore else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('FujiNet split XEX', 'reboot' if restore else 'boot/save','passed',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fujinet-pc',type=Path,required=True)
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--menu',action='store_true',help='Boot FujiNet CONFIG, then press its physical OPTION switch')
    parser.add_argument('--manual',action='store_true',help='Interrupt into Forth and exercise an emitted ROM-SIO CODE word before EXEC816')
    args=parser.parse_args();check(args.bundle.resolve(),args.output.resolve(),args.fujinet_pc.resolve(),args.restore,args.menu,args.manual)
