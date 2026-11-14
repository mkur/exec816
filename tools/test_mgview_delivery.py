#!/usr/bin/env python3
"""Audit the MGVIEW demo and optionally cold-boot only to verified native entry."""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
from c_program import ABI
from filesystem_audit import Audit
from native_program import ROOT,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_bootable_atr import DiskBoot
from test_mouse_observe import BRIDGE,ROM,PIN


def run(bundle,output,tested,boot=False):
    bundle=bundle.resolve();output=output.resolve();output.mkdir(parents=True,exist_ok=True)
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
    require(audit.files['MGVIEW.TXT']==(ROOT/'ports/magic/mgview/sample.txt').read_bytes(),'Sample bytes were converted')
    previous=json.loads(tested.read_text())
    apps={}
    for name in ('mgview','counter'):
        raw=audit.files['C/'+name.upper()+'.APP'];digest=hashlib.sha256(raw).hexdigest()
        require(digest==previous['app_sha256'][name],'Packaged APP differs from tested binary: '+name)
        require(digest==sha256(bundle/'bitmap-console/apps'/name/'program.app'),'APP differs from build: '+name)
        apps[name]=digest
    headers={name:struct.unpack_from('<H',raw,6)[0] for name,raw in audit.files.items() if name.endswith('.APP')}
    require(all(version==ABI['version'] for version in headers.values()),'Stale APP ABI on SYS')
    report=dict(status='pass',tier='development',qualification=False,zip_sha256=sha256(bundle/'exec816-demo.zip'),
        app_sha256=apps,system_app_headers=headers,sample_bytes=len(audit.files['MGVIEW.TXT']),
        allocation=allocation,qed_executed=False,cold_boot='not run; explicit opt-in only',
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,private_idle=0,per_public_task=0))
    if boot:
        program=read_build(bundle);loader=DiskBoot(bundle)
        with emulator(BRIDGE,ROM,output,pin=PIN) as bridge:
            for key,value in PIN['configuration'].items():bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
            bridge.mount(0,str(bundle/'exec816.atr'));report['machine']=verify_machine(bridge,ROM,PIN)
            loader(bridge,program)
        report['cold_boot']=loader.report
        report['boot_scope']='ROM SIO through OF816 countdown to byte-verified native entry; no interactive desktop qualification.'
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('MGVIEW package audit'+(' and cold native-entry boot' if boot else '')+' passed')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/gem-mgview/demo')
    parser.add_argument('--output',type=Path,default=ROOT/'build/gem-mgview/delivery')
    parser.add_argument('--tested',type=Path,default=ROOT/'build/mgview-dev/smoke/results-reference.json')
    parser.add_argument('--cold-boot',action='store_true',help='Explicitly request the longer ROM/OF816 transport check')
    args=parser.parse_args();run(args.bundle,args.output,args.tested,args.cold_boot)
