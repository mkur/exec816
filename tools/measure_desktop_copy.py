#!/usr/bin/env python3
"""Compare desktop copy chunks on explicit experimental media, using physical input.

The resident system and packaged OF816 boot remain unchanged. Only a rebuilt
DESKTOP.APP differs, with an emitted layout probe for the experimental buffer.
Guest memory is observed, not patched. Run each case in a fresh output directory.
"""
import argparse
from program_image_layout import FIELDS as IMAGE_FIELDS
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from browser_model import FIELDS as F, select, wait_listing
from colour_desktop_model import FIELDS as D, JOB_FIELDS as C, LAYOUT
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import symbols
from loadable_gem_feedback import measure
from native_program import ROOT, require, sha256
from sdfs_reference import extract, make
from sio_transaction_trace import BASE_HZ
from stack_budget import stack_usage
from test_demo import run
from test_shell_core import KEYS

SMALL = bytes(range(256))*128 + bytes(range(37))
LARGE = bytes(range(256))*512


def variant(out, size):
    from build_c_program import build
    source = out/'copy-source'
    shutil.copytree(ROOT/'examples/gem-browser', source)
    header = source/'desktop.h'
    original = header.read_text()
    import re
    changed, count = re.subn(r'COPY_BUFFER_BYTES=\d+', f'COPY_BUFFER_BYTES={size}', original)
    require(count == 1, 'Expected one desktop copy buffer')
    header.write_text(changed)
    header = source/'browser.h'
    header.write_text(header.read_text().replace('../../c/calypsi/file-list.h',
                                               str(ROOT/'c/calypsi/file-list.h')))
    probe = source/'layout.c'
    probe.write_text((ROOT/'tests/programs/gem_colour_desktop_layout.c').read_text().replace(
        '../../examples/gem-browser/desktop.h', str(source/'desktop.h')))
    layout = LAYOUT
    app = build(out/'bitmap-console/apps/desktop',
                [source/'desktop-main.c', source/'browser.c', ROOT/'c/calypsi/file-list.c'],
                probes=[(probe, layout)])
    media = out/'comparison-files'
    extract(out/'system.atr', media)
    shutil.copyfile(out/'bitmap-console/apps/desktop/program.app', media/'C/DESKTOP.APP')
    manifest = json.loads((out/'demo-manifest.json').read_text())
    geometry = manifest['mounts'][0]
    disk = out/'comparison-system.atr'
    make(disk, media, geometry['sectors'], geometry['sector_bytes'])
    provenance = dict(buffer_bytes=size, application_sha256=app['sha256'],
        original_sources={str(p.relative_to(ROOT)):sha256(p)
            for p in (ROOT/'examples/gem-browser').iterdir() if p.is_file()},
        experimental_sources={p.name:sha256(p) for p in source.iterdir() if p.is_file()},
        layout=app['image']['provenance']['checked_layout'])
    (out/'copy-variant.json').write_text(json.dumps(provenance, indent=2)+'\n')
    return disk, provenance


class CopyProbe:
    def __init__(self, count, shell):
        self.count, self.shell = count, shell
        self.results = {}

    def prepare_work(self, target, item):
        with tempfile.TemporaryDirectory(prefix='exec816-copy-') as tmp:
            root = Path(tmp)
            (root/'SOURCE.BIN').write_bytes(SMALL)
            (root/'BIG.BIN').write_bytes(LARGE)
            make(target, root, item['sectors'], item['sector_bytes'])

    def exercise(self, s):
        b = s.b
        directory = s.p['output']/'bitmap-console'
        resident = json.loads((directory/'c-image.json').read_text())['symbols']
        sy = symbols(b, s.p, directory, 'desktop', s.number(resident['GEMDesktopChildren'], 4))
        desk = sy['GEMDesk']
        base = s.number(desk+D['folders'], 4)
        job = lambda: s.number(desk+D['job'], 4)
        clock = lambda: b.eval_expr('@clk') & 0xffffffff
        seconds = lambda start: ((clock()-start) & 0xffffffff)/BASE_HZ
        text = lambda name: b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
        def checkpoint():
            (s.p['output']/'copy-samples.json').write_text(json.dumps(self.results,indent=2)+'\n')
        # Private native layouts: DosRegistry.runtime, FSTYPES.Service.packet.
        # Their leading pointer-only fields have no alignment gaps. Observe
        # public packet actions at bank-zero IRQ checkpoints: BP_SET on the
        # pinned bridge cannot address upper-bank C routines.
        service=s.number(s.p['build']['memory']['dos_storage']['SHARED']+68,3)
        packet_at=service+42
        packet='(dw($%x)+db($%x)*65536)'%(packet_at,packet_at+2)
        abi=json.loads((ROOT/'abi/dos.json').read_text())
        fields={n:o for n,_,o in abi['records']['DosPacket']['fields']}
        packet_base=abi['records']['StandardPacket']['fields'][1][2]
        def action(name):
            return '(%s!=0)&(dw(%s+%d)=%d)'%(packet,packet,packet_base+fields['dp_Type'],abi['actions']['ACTION_'+name])
        active='((dw($%x)|dw($%x))!=0)'%(desk+D['job'],desk+D['job']+2)
        def wait_phase(name):s.rendezvous(active+'&'+action(name.upper()))
        b.eval_expr(active+'&'+action('READ'))
        print('Copy observer ready',hex(service),flush=True)
        def at(name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old = [s.number(at(n),2) for n in ('cursorX','cursorY')]
            position = schedule(b,s.p,old,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%
                         (at('cursorX'),position[0],at('cursorY'),position[1]))
            s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        def key(name,shift=False):
            if shift:b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up')
            if shift:b._cmd_ok('KEY SHIFT up')
            s.frames(35)
        def fill(value):
            for _ in text('editText'):key('BACKSPACE')
            for c in value:key(*KEYS[c])
        def closed(expected=None):
            s.rendezvous('dw($%x)=0'%(base+F['dialog']))
            if expected:
                # Copy retirement precedes the synchronous folder refresh.
                # Wait for its published result rather than assuming the
                # next fixed number of frames covers directory I/O.
                value=expected.encode('ascii')
                condition='&'.join('(db($%x)=%d)'%(base+F['status']+i,v)
                                   for i,v in enumerate(value))
                s.rendezvous(condition)
            s.frames(100)
        menus = Menus(s,click,move)
        menus.select('SYS:')
        # Start the same independent panel before every throughput comparison.
        click(296,8);click(304,40);s.frames(500)
        panel = symbols(b,s.p,directory,'panel',s.number(desk+D['children'],4))['GEMPanel']
        menus.select('Control Panel')
        if self.count:
            measure(s,panel,move,'idle',count=self.count)
            self.results['idle_panel']=s.saved['loaded_panel_feedback']['idle'];checkpoint()
        menus.select('SYS:')
        key('P');s.rendezvous('dw($%x)=1'%(base+F['dialog']))
        fill('WORK:');key('RETURN');closed();wait_listing(s,base)
        require(text('path')=='WORK:','Expected writable folder')

        def start(source,target):
            print('Starting desktop copy',source,target,flush=True)
            select(s,base,source,click)
            click(152,8);click(168,24+7*16)
            s.rendezvous('dw($%x)=4'%(base+F['dialog']))
            fill('WORK:'+target)
            b._cmd_ok('KEY RETURN down');s.frames(3);b._cmd_ok('KEY RETURN up')
            wait_phase('Read')
            require(job() and s.number(job()+C['copied'],4)==0,'Missed first payload read')
            return clock()

        start_time = start('SOURCE.BIN','DESKTOP.BIN')
        s.rendezvous('dw($%x)=%d'%(job()+C['copied'],len(SMALL)))
        transfer_seconds = seconds(start_time)
        require(s.number(job()+C['copied'],4)==len(SMALL),'Wrong desktop byte count')
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2))
        complete_seconds = seconds(start_time)
        closed('Copy complete')
        require(text('status').startswith('Copy complete'),'Desktop copy failed: '+text('status'))
        self.results['desktop']=dict(bytes=len(SMALL),transfer_seconds=transfer_seconds,
            finalized_seconds=complete_seconds,bytes_per_second=len(SMALL)/complete_seconds,
            scope='First active READ packet to copy job retirement after close/rename, sampled at IRQ; transfer ends when copied count reaches file size.')
        print('Desktop transfer',self.results['desktop'],flush=True);checkpoint()

        self.results['cancel']=[]
        for phase in ('Read','Write'):
            start('BIG.BIN','CANCEL.BIN')
            if phase=='Write':s.rendezvous(active+'&'+action('WRITE'))
            cancel_start=clock();b._cmd_ok('KEY ESC down')
            s.rendezvous(active+'&'+action('END'))
            accepted_seconds=seconds(cancel_start)
            b._cmd_ok('KEY ESC up')
            s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2))
            elapsed=seconds(cancel_start)
            closed('Copy cancelled')
            require(text('status').startswith('Copy cancelled'),'Cancellation failed: '+text('status'))
            record=dict(phase=phase,accepted_seconds=accepted_seconds,cleanup_seconds=elapsed,
                scope='Escape injected during first active data packet; acceptance at first END packet, cleanup at job retirement, sampled at IRQ.')
            self.results['cancel'].append(record);print('Cancel',record,flush=True);checkpoint()

        if self.count:
            start('BIG.BIN','LOADED.BIN')
            menus.select('Control Panel')
            require(job(),'Copy completed before loaded feedback')
            measure(s,panel,move,'copy',count=self.count)
            require(job(),'Copy completed during loaded feedback')
            self.results['copy_panel']=s.saved['loaded_panel_feedback']['copy'];checkpoint()
            menus.select('WORK:');key('ESC');closed('Copy cancelled')
            require(text('status').startswith('Copy cancelled'),'Loaded copy was not cancelled')

        menus.select('Shell')
        if self.shell:
            print('Starting shell 16 KiB COPY',flush=True)
            process=json.loads((ROOT/'abi/process.json').read_text())
            offsets={n:o for n,_,o in process['record']}
            table=s.p['build']['memory']['process_storage']['BASE']
            free=[table+i*process['record_bytes'] for i in range(1,8)
                  if s.number(table+i*process['record_bytes']+offsets['state'],1)==0]
            previous=s.begin('COPY WORK:SOURCE.BIN WORK:SHELL.BIN')
            s.rendezvous('|'.join('(db($%x)=2)'%(row+offsets['state']) for row in free))
            row=next(row for row in free if s.number(row+offsets['state'],1)==2)
            image=s.number(row+offsets['image'],3)
            profile=json.loads((s.p['output']/'COPY.profile.json').read_text())
            buffer=next(o for o in profile['objects'] if '_COPY_TRANSFERBUFFER_' in o['name'])
            require(buffer['size']==16384 and buffer['location']['section']=='Bss','Changed shell COPY buffer')
            address=s.number(image+IMAGE_FIELDS['bss'],3)+buffer['location']['offset']
            arg=packet_base+fields['dp_Arg2']
            target='(dw(%s+%d)=%d)&(db(%s+%d)=%d)'%(packet,arg,address&65535,packet,arg+2,address>>16)
            s.rendezvous(action('READ')+'&'+target);start_time=clock()
            s.rendezvous(action('END'));transfer_seconds=seconds(start_time)
            s.ready(previous);complete_seconds=seconds(start_time);s.result()
            self.results['shell']=dict(buffer_bytes=16384,bytes=len(SMALL),
                transfer_seconds=transfer_seconds,ready_seconds=complete_seconds,
                bytes_per_second=len(SMALL)/complete_seconds,
                scope='First observed READ packet to shell readiness; transfer ends at first END packet, sampled at IRQ.')
            print('Shell transfer',self.results['shell'],flush=True);checkpoint()
        self.results['stacks']=stack_usage(b,s.p['build']['memory']);checkpoint()
        s.save_screen(s.p['output']/'boot-smoke.png')
        for c in 'EXIT':s.press(c)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--buffer',type=int,choices=(512,1024,2048,16384),required=True)
    parser.add_argument('--count',type=int,default=40)
    parser.add_argument('--shell',action='store_true')
    parser.add_argument('--reuse',action='store_true',help='Reuse this experiment\'s built application and system disk')
    args=parser.parse_args();out=args.output.resolve()
    if args.reuse:
        provenance=json.loads((out/'copy-variant.json').read_text())
        require(provenance['buffer_bytes']==args.buffer,'Wrong reused buffer size')
        disk=out/'comparison-system.atr'
    else:
        require(not out.exists(),'Use a fresh measurement directory')
        shutil.copytree(args.bundle.resolve(),out,
            ignore=shutil.ignore_patterns('extracted','g4bench-extracted-*','*.log','*.bgra','*.png'))
        with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
        disk, provenance=variant(out,args.buffer)
    probe=CopyProbe(args.count,args.shell)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
        integration=probe,profile_commands=False,measurement_commands=[],
        media_path=disk,measurement_media_sha256=sha256(disk))
    with tempfile.TemporaryDirectory(prefix='exec816-copy-readback-') as tmp:
        root=Path(tmp);extract(out/'work-walkthrough.atr',root)
        require((root/'SOURCE.BIN').read_bytes()==SMALL,'Source changed')
        require((root/'BIG.BIN').read_bytes()==LARGE,'Large source changed')
        require((root/'DESKTOP.BIN').read_bytes()==SMALL,'Desktop copy bytes differ')
        if args.shell:require((root/'SHELL.BIN').read_bytes()==SMALL,'Shell copy bytes differ')
        for name in ('EXECCOPY.TMP','CANCEL.BIN','LOADED.BIN'):
            require(not (root/name).exists(),'Cancellation left '+name)
    result.update(tier='development',qualification=False,copy=probe.results,variant=provenance,
        comparison_media_sha256=sha256(disk),zip_sha256=sha256(out/'exec816-demo.zip'),
        independent_readback=True,bank_zero_delta=dict(fixed=0,per_public_task=0,idle=0))
    (out/'copy-results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
