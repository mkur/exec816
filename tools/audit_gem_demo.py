#!/usr/bin/env python3
"""Audit the distributable GEM ZIP against its frozen build and SYS contents."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

from filesystem_audit import Audit
from native_program import require, sha256


def audit(bundle):
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    require(manifest['gem_desktop'] and manifest['bootable_atr'],
            'Expected a combined GEM desktop package')
    require(all(sha256(bundle/name)==digest for name,digest in
                manifest['artifacts'].items()),'Changed recorded build artifact')
    archive=bundle/'exec816-demo.zip'
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();root='exec816-demo/'
        require(len(names)==len(set(names)),'Duplicate ZIP members')
        require(all(n.startswith(root) and '..' not in PurePosixPath(n).parts
                    for n in names),'Unexpected ZIP path')
        members={n[len(root):]:z.read(n) for n in names}
    checksums={}
    for line in members['SHA256SUMS'].decode('ascii').splitlines():
        digest,name=line.split('  ',1)
        require(name not in checksums,'Duplicate checksum')
        checksums[name]=digest
    require(set(checksums)==set(members)-{'SHA256SUMS'},'Incomplete checksums')
    require(all(hashlib.sha256(members[n]).hexdigest()==h for n,h in checksums.items()),
            'ZIP checksum mismatch')
    allowed={'Exec-of816.xex','README.txt','SHA256SUMS','altirraos-816.rom',
        manifest['media'],'cartridge/Exec-of816-atarimax-8mbit-new.car',
        'cartridge/Exec-of816-atarimax-8mbit-old.car',
        'cartridge/Exec-of816-atarimax-8mbit.bin','cartridge/README.txt'}
    require(all(n in allowed or n.startswith('licenses/') for n in members),
            'Development artifacts in distributable ZIP')
    require(allowed<=members.keys(),'Missing boot artifact or cartridge form')
    for name in ('OF816-LICENSE.txt','ALTIRRAOS-LICENSE.txt','EXEC816-GPL-3.0.txt',
                 'EXEC816-MIT.txt','GEM-COPYING.txt','SDX-UTILITIES-NOTICE.txt'):
        require('licenses/'+name in members,'Missing upstream notice '+name)
    boot=json.loads((bundle/'of816/of816.json').read_text())
    require(checksums['Exec-of816.xex']==boot['xex_sha256'],'Changed OF816 image')
    require(members[manifest['media']]==(bundle/manifest['media']).read_bytes(),
            'ZIP and production SYS differ')
    disk=Audit(members[manifest['media']]);allocation=disk.sdfs()
    for name,record in manifest['files'].items():
        require(name in disk.files and hashlib.sha256(disk.files[name]).hexdigest()
                ==record['sha256'],'Stale SYS input '+name)
    for name,app in manifest['kernel']['gem_applications'].items():
        if name=='desktop':continue
        name='C/'+name.upper()+'.APP'
        require(hashlib.sha256(disk.files[name]).hexdigest()==app['sha256'],
                'SYS APP does not match its provider: '+name)
    for name in ('C/TERMINAL.APP','C/MD5.COM','C/ARC.COM','C/ARCADD.OVL',
                 'C/ARCEXT.OVL','C/ARCLST.OVL','C/EDX.COM','WORK/SAMPLE.TXT'):
        require(name in disk.files,'Missing distribution file '+name)
    require(b'GEM desktop and terminal' in members['README.txt'],
            'Missing terminal instructions')
    return dict(status='pass',tier='development',qualification=False,
        zip_sha256=sha256(archive),zip_bytes=archive.stat().st_size,
        members=sorted(members),checksums=checksums,allocation=allocation,
        matched_system_files=len(manifest['files']),
        matched_disk_apps=len(manifest['kernel']['gem_applications'])-1,
        qed_separate=bool(manifest.get('qed')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();record=audit(args.bundle.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('GEM ZIP/SYS audit passed:',record['matched_system_files'],'files')
