#!/usr/bin/env python3
"""Audit the MGVIEW demo and optionally smoke-test the combined boot disk."""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
from c_program import ABI
from filesystem_audit import Audit
from native_program import ROOT,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_bootable_atr import DiskBoot
from test_mouse_observe import BRIDGE,ROM,PIN


def exercise_viewer(bridge,program,bundle,output,report,sample):
    from gem_applications import MODELS,instances
    from gem_render_oracle import font_bytes
    from measure_mgview import expected
    from test_gem_acceptance import Session

    directory=bundle/'bitmap-console'
    session=Session(bridge,program,directory,output,report)
    MODELS['mgview']=('nwindows',0,0)
    bridge._cmd_ok('KEY ALL up')
    bridge._cmd_ok('MOUSE ST')
    for _ in range(40):
        session.frames(200)
        found=[row for row in instances(bridge,program,directory) if row['name']=='mgview']
        if len(found)==1 and session.number(found[0]['symbols']['nwindows'],2)==1:
            break
    else:
        from console_model import read_cells

        bridge.screenshot(str(output/'startup-failure.png'))
        source=session.source(0)
        transcript=read_cells(session.far,source).decode('latin1') if source else ''
        (output/'startup-console.txt').write_text(transcript)
        raise RuntimeError('MGVIEW did not open the startup document; see startup-console.txt')
    window=session.number(found[0]['symbols']['windows'])
    session.move(632,0)
    session.frames(60)
    work=tuple(session.number(window+268+2*i,2) for i in range(4))
    x,y,w,h=work
    require(w>0 and h>0,'Missing MGVIEW work area')
    font=font_bytes(directory/'selected/src/vdi/font8x8.c')
    viewport=[]
    for shift in (0,1):
        if shift:
            bridge._cmd_ok('KEY CTRL down')
            bridge._cmd_ok('KEY EQUALS down')
            session.frames(3)
            bridge._cmd_ok('KEY EQUALS up')
            bridge._cmd_ok('KEY CTRL up')
            session.frames(60)
        require(session.number(window+280)==shift,'MGVIEW vertical shift differs')
        path=output/f'viewer-{shift}.bgra'
        frame=bridge.rawscreen(str(path))
        raw=path.read_bytes()
        actual=b''.join(raw[row*frame.stride+(col+16)*4:row*frame.stride+(col+16)*4+3]
                        for row in range(y,y+h) for col in range(x,x+w))
        bridge.screenshot(str(output/f'viewer-{shift}.png'))
        require(actual==expected(font,work,sample,shift),'MGVIEW viewport differs from sample')
        viewport.append(dict(shift=shift,sha256=hashlib.sha256(actual).hexdigest()))
    report['viewer']=dict(work=work,viewport=viewport,live_tasks=session.live())
    bridge._cmd_ok('KEY CTRL down')
    bridge._cmd_ok('KEY Q down')
    bridge.bp_clear_all()


def run(bundle,output,tested,boot=False):
    bundle=bundle.resolve();output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    demo=json.loads((bundle/'demo-manifest.json').read_text())
    only=bool(demo.get('mgview_only'))
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        files={name.removeprefix('exec816-demo/'):archive.read(name) for name in archive.namelist()}
    for name in files:
        require(name.startswith('licenses/') or name in ('README.txt','SHA256SUMS') or
            (Path(name).parent==Path('cartridge') and
                (Path(name).suffix in ('.car','.bin') or Path(name).name=='README.txt')) or
            ('/' not in name and Path(name).suffix in ('.xex','.atr','.rom','.car')),
            'Development file escaped into ZIP: '+name)
    sums={name:digest for digest,name in (line.split('  ',1) for line in files['SHA256SUMS'].decode().splitlines())}
    require(set(sums)==set(files)-{'SHA256SUMS'},'Incomplete ZIP checksums')
    for name,digest in sums.items():require(hashlib.sha256(files[name]).hexdigest()==digest,'Changed ZIP member: '+name)
    require(files['licenses/MGVIEW-COPYING.txt']==(ROOT/'ports/magic/mgview/upstream/LICENSE').read_bytes(),'Changed MagiC licence')
    require('licenses/MGVIEW-NOTICE.txt' in files and 'qed.atr' not in files,'Incorrect application notices/media')
    audit=Audit(files['exec816.atr']);allocation=audit.sdfs()
    sample=audit.files['MGVIEW.TXT']
    require(sample==(ROOT/'ports/magic/mgview/sample.txt').read_bytes(),'Sample bytes were converted')
    if tested is None and not only:
        tested=ROOT/'build/mgview-dev/smoke/results-reference.json'
    previous=json.loads(tested.read_text()) if tested else None
    apps={}
    for name in (('mgview',) if only else ('mgview','counter')):
        raw=audit.files['C/'+name.upper()+'.APP'];digest=hashlib.sha256(raw).hexdigest()
        if previous is not None:
            require(digest==previous['app_sha256'][name],'Packaged APP differs from tested binary: '+name)
        require(digest==sha256(bundle/'bitmap-console/apps'/name/'program.app'),'APP differs from build: '+name)
        apps[name]=digest
    headers={name:struct.unpack_from('<H',raw,6)[0] for name,raw in audit.files.items() if name.endswith('.APP')}
    require(all(version==ABI['version'] for version in headers.values()),'Stale APP ABI on SYS')
    if only:
        require(set(headers)=={'C/MGVIEW.APP'},'Additional GEM applications on the MGVIEW-only disk')
        require(audit.files['S/STARTUP'].splitlines()[-2:]==[b'C:MGVIEW.APP SYS:MGVIEW.TXT',b'EXIT'],
                'Missing foreground startup and exit for MGVIEW')
    report=dict(status='pass',tier='development',qualification=False,zip_sha256=sha256(bundle/'exec816-demo.zip'),
        app_sha256=apps,system_app_headers=headers,sample_bytes=len(audit.files['MGVIEW.TXT']),
        allocation=allocation,qed_executed=False,cold_boot='not run; explicit opt-in only',
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,private_idle=0,per_public_task=0))
    if boot:
        from test_dos_stack import execute,ownership

        program=read_build(bundle);loader=DiskBoot(bundle)
        loader.snapshots=output/'disk-boot'
        loader.snapshots.mkdir(exist_ok=True)
        image=output/'exec816.atr'
        image.write_bytes(files['exec816.atr'])
        rom=output/ROM.name
        rom.write_bytes(files[ROM.name])
        with emulator(BRIDGE,rom,output,pin=PIN) as bridge:
            for key,value in demo['configuration'].items():bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
            bridge.mount(0,str(image));report['machine']=verify_machine(bridge,rom,PIN)
            loader(bridge,program)
            if only:
                def before(guest):
                    exercise_viewer(guest,program,bundle,output,report,sample)
                report['exit'],_=execute(bridge,{**program,'output':output},preloaded=True,before_run=before)
                bridge._cmd_ok('KEY ALL up')
                ownership(bridge,program,program['output'])
        report['cold_boot']=loader.report
        report['boot_scope']='MGVIEW auto-open, scroll and clean system exit' if only else 'ROM SIO through OF816 countdown to byte-verified native entry'
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('MGVIEW package audit'+(' and cold boot smoke' if boot else '')+' passed')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/gem-mgview/demo')
    parser.add_argument('--output',type=Path,default=ROOT/'build/gem-mgview/delivery')
    parser.add_argument('--tested',type=Path,help='Compare application hashes with a prior functional run')
    parser.add_argument('--cold-boot',action='store_true',help='Explicitly request the longer ROM/OF816 transport check')
    args=parser.parse_args();run(args.bundle,args.output,args.tested,args.cold_boot)
