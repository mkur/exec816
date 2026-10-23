#!/usr/bin/env python3
"""Cold-boot the packaged ATR through ROM SIO, then native persistence checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import zipfile

from native_program import ROOT, require, sha256
from test_demo import run
from test_of816 import (check_boot_guards, check_loading_paused, check_loading_complete,
                       enter_forth, press)
from filesystem_audit import Audit


def wait_at(b, target, failures=(), timeout=900,condition=None):
    b.bp_clear_all()
    for address in (target,*failures):
        expression=f'@xpc=${address:x}'
        if condition:expression=f'({expression})&({condition})'
        b.bp_set(address&0xffff,condition=expression)
    b.resume();deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        pc=b.eval_expr('@xpc')
        if pc in (target,*failures):
            if condition and not b.eval_expr(condition):
                time.sleep(.05);continue
            b.pause();require(pc==target,f'Disk boot failed at ${pc:04x}')
            return
        time.sleep(.05)
    b.pause();raise RuntimeError(f'Disk boot timeout: {b.regs()}')


class DiskBoot:
    def __init__(self,bundle,manual=False,peer=False,native_snapshot=None):
        self.bundle,self.manual=bundle,manual
        self.monitor=json.loads((bundle/'of816/of816.json').read_text())
        self.reader=json.loads((bundle/'boot-media/boot-atr.json').read_text())
        self.report={}
        self.snapshots=bundle/('fuji-boot' if peer else 'disk-boot')
        self.snapshots.mkdir(exist_ok=True)
        self.native_snapshot=native_snapshot

    def __call__(self,b,p):
        mon=self.monitor;labels=mon['labels']
        reader=self.reader['reader']['disk-boot-reader.s']['labels']
        first=self.reader['reader']['disk-boot-first.s']['labels']
        failures=(reader['reader_failed'],first['first_failed'])
        if self.native_snapshot:
            b.state_load(str(self.native_snapshot))
            self.report=dict(native_entry_replay=str(self.native_snapshot),
                             snapshot_sha256=sha256(self.native_snapshot))
            self.verify_native(p,self.native_snapshot)
            wait_at(b,p['labels']['start'],(),30);b.bp_clear_all()
            return
        b.cold_reset()
        wait_at(b,reader['reader_start'],failures,90)
        self.report['first_stage_rom_boot']=True
        self.report['memlo']=b.peek16(0x2e7)
        require(self.report['memlo']<=0xa00,'Disk reader concealed firmware reservations')
        wait_at(b,labels['of_start'],failures,180)
        settings=check_loading_paused(b,mon,p)
        self.report['firmware_to_of_frame']=b.eval_expr('@frame')
        vectors=b.memdump(0x256,9);iocb=b.memdump(0x340,32)
        b.state_save(str(self.snapshots/'before-of.altstate2'))
        if self.manual:
            self.report['manual']=enter_forth(b,labels)
            for character in 'decimal 128 CACHE-BLOCKS! 0 BOOT-VERBOSE!\n':press(b,labels,character)
            settings=b.memdump(mon['boot_config']['address'],8)
            for character in 'EXEC816':press(b,labels,character)
            press(b,labels,'\n',labels['of_handoff'])
        else:
            wait_at(b,labels['of_autoboot'],failures,30)
            start=b.eval_expr('@frame')
            wait_at(b,labels['of_handoff'],failures,30)
            self.report['countdown_frames']=b.eval_expr('@frame')-start
            require(249<=self.report['countdown_frames']<=251,'Wrong disk-boot countdown')
        check_boot_guards(b,mon['layout'])
        wait_at(b,p['labels']['loader_start'],failures,900)
        check_loading_complete(b,mon,p,settings)
        require(b.memdump(0x256,9)==vectors and b.memdump(0x340,32)==iocb,
                'Disk callback did not restore firmware context')
        require(b.peek(reader['reader_error'])==b'\0','Reader error before native handoff')
        self.report.update(native_handoff_frame=b.eval_expr('@frame'),
            callbacks=b.peek16(reader['reader_callbacks']),reads=b.peek16(reader['reader_reads']),
            source_bytes=int.from_bytes(b.memdump(reader['file_offset'],3),'little'),
            reader_guards='intact',firmware_context_restored=True)
        print('ATR loaded OF816/kernel:',self.report,flush=True)
        b.state_save(str(self.snapshots/'before-native.altstate2'))
        self.verify_native(p,self.snapshots/'before-native.altstate2')
        # The existing loader prints its final partial progress dot before
        # native entry. Snapshot the OS screen only after that transport work.
        wait_at(b,p['labels']['start'],(),30)
        b.bp_clear_all()

    def verify_native(self,p,path):
        with zipfile.ZipFile(path) as snapshot:
            memory=snapshot.read('high-memory.bin')
        verified=0
        for span in p['image']['segments']:
            address=span['address'];wanted=bytes(span['bytes'])
            require(memory[address-65536:address-65536+len(wanted)]==wanted,
                    f'Expanded native bytes differ at ${address:x}')
            verified+=len(wanted)
        for span in p['image']['zero_fill']:
            address=span['address'];size=span['size']
            require(memory[address-65536:address-65536+size]==bytes(size),
                    f'Native zero-fill differs at ${address:x}')
            verified+=size
        self.report['native_bytes_verified']=verified


class Workspace:
    interrupt_marker='native_nmi'

    def __init__(self,restore=False):
        self.restore=restore

    def exercise(self,s):
        s.saved.setdefault('desktop_menu',{})
        from desktop_menu_check import Menus
        from desktop_mouse import schedule
        from gem_applications import symbols
        from colour_desktop_model import FIELDS as DESK
        directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        sy=symbols(s.b,s.p,directory,'desktop',s.number(resident['GEMDesktopChildren'],4))
        desk=sy['GEMDesk']
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            position=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            position=schedule(s.b,s.p,position,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(12)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(30)
        menus=Menus(s,click,move)
        s.rendezvous('dw($%x)=1'%(desk+DESK['ready']))
        if self.restore:
            require(s.number(desk+DESK['settingsLoaded'],2)==1,'Desktop settings did not survive disk boot')
        menus.select('Shell')
        s.command('ASSIGN',b'WORK: -> D1:WORK')
        mounts=s.command('MOUNT',b'D1:')
        require(b'D8:' not in mounts,'Unexpected required second disk')
        s.command('HELLO',b'Hello from disk!')
        if self.restore:
            s.command('CAT WORK:BOOT.BAS',b'PRINT 42')
            s.command('FB WORK:BOOT.BAS',b'42')
            s.command('CAT WORK:PERSIST.TXT',b'persisted')
            s.command('CMP SYS:STORY.TXT WORK:COPY.TXT')
            s.command('DIR WORK:',b'DESKTOP.CFG')
        else:
            s.command('ECHO "PRINT 42" >WORK:BOOT.BAS')
            s.command('FB WORK:BOOT.BAS',b'42')
            s.command('ECHO persisted >WORK:PERSIST.TXT')
            s.command('COPY SYS:STORY.TXT WORK:COPY.TXT')
            s.command('CMP SYS:STORY.TXT WORK:COPY.TXT')
            s.command('MAKEDIR WORK:TEMP')
            s.command('ECHO temporary >WORK:TEMP/OLD.TXT')
            s.command('RENAME WORK:TEMP/OLD.TXT WORK:TEMP/NEW.TXT')
            s.command('DELETE WORK:TEMP/NEW.TXT')
            s.command('DELETE WORK:TEMP')
            # Boot files are normal allocated files with normal DOS protection.
            previous=s.begin('DELETE SYS:BOOT.LDR');s.ready(previous);s.result(222)
            menus.select('SYS:')
            click(296,8);click(304,28+5*11);s.frames(120)
            require(not s.number(desk+DESK['error'],4),'Save Settings on boot disk failed')
            menus.select('Shell')
        s.save_screen(s.p['output']/('atr-restored.png' if self.restore else 'atr-workspace.png'))
        s.save_screen(s.p['output']/'boot-smoke.png')
        for character in 'EXIT':s.press(character)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def check(bundle,manual=False,restore=False,firmware=None,native_snapshot=None):
    extracted=bundle/'atr-extracted'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            require(hashlib.sha256(archive.read('exec816-demo/'+name)).hexdigest()==digest,'ZIP checksum mismatch')
        require('exec816-demo/exec816.atr' in archive.namelist(),'No bootable ATR in ZIP')
        require(not any(Path(n).name in ('system.atr','work.atr') for n in archive.namelist()),'Split media in single-disk ZIP')
        archive.extractall(extracted)
    media=bundle/('atr-fujinet.atr' if firmware else 'atr-walkthrough.atr')
    if not restore:shutil.copyfile(extracted/'exec816-demo/exec816.atr',media)
    initial_sha256=sha256(media)
    boot=DiskBoot(bundle,manual,bool(firmware),native_snapshot)
    if firmware:
        from fujinet_pc_peer import FujiNetPC
        with FujiNetPC(bundle/'fujinet-peer',media,firmware) as peer:
            result=run(bundle,boot_smoke=True,bootstrap=boot,media_path=media,
                       integration=Workspace(restore),expected_cache=128 if manual else None,sio_peer=peer,
                       emulator_output=bundle/'fujinet-emulator')
            require(not peer.error,'FujiNet relay failed: '+str(peer.error))
        result['fujinet_pc']=dict(binary=str(firmware),sha256=sha256(firmware),
            relay=json.loads((bundle/'fujinet-peer/relay.json').read_text()))
    else:
        result=run(bundle,boot_smoke=True,bootstrap=boot,media_path=media,
                   integration=Workspace(restore),expected_cache=128 if manual else None)
    audit=Audit(media.read_bytes());allocation=audit.sdfs()
    require(b'PRINT 42' in audit.files['WORK/BOOT.BAS'] and
            b'persisted' in audit.files['WORK/PERSIST.TXT'],'Saved bytes missing')
    require(audit.files['WORK/DESKTOP.CFG'].startswith(b'EXEC816_DESKTOP 1\n'),'Saved desktop preferences missing')
    from build_bootable_atr import Volume
    current=Volume(media.read_bytes())
    original=Volume((extracted/'exec816-demo/exec816.atr').read_bytes())
    # SDFS may update its volume header; executable bytes and locator must stay.
    require(current.image.sector(1)[:9]==original.image.sector(1)[:9] and
            current.image.sector(1)[40:]==original.image.sector(1)[40:] and
            all(current.image.sector(n)==original.image.sector(n) for n in (2,3)),
            'Boot header/code/locator changed during saves')
    require(all(current.entry(n)[0][0]&1 for n in ('BOOT.LDR','EXEC816.XEX')),
            'Boot-file protection lost')
    result.update(status='pass',tier='development',qualification=False,atr_boot=boot.report,
                  persisted=restore,allocation=allocation,media_sha256=sha256(media),
                  initial_media_sha256=initial_sha256,
                  boot_xex_sha256=boot.reader['xex_sha256'],
                  boot_code_locator_and_protection='intact')
    target=bundle/(('atr-fujinet-' if firmware else 'atr-')+('reboot-results.json' if restore else 'boot-results.json'))
    target.write_text(json.dumps(result,indent=2)+'\n')
    print('Single-disk ATR', 'reboot' if restore else 'boot/save','passed',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--manual',action='store_true')
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--fujinet-pc',type=Path,help='Real local FujiNet-PC executable, isolated config and NetSIO peer')
    parser.add_argument('--native-snapshot',type=Path,help='Development-only replay of a verified pre-native snapshot; not a cold-boot claim')
    args=parser.parse_args();check(args.bundle.resolve(),args.manual,args.restore,args.fujinet_pc,args.native_snapshot)
