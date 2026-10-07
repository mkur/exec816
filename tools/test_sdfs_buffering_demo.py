#!/usr/bin/env python3
"""Focused Write smoke on exact archived shell-only XEX and cartridge bytes."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from filesystem_audit import Audit
from native_program import ROOT, require, sha256
from package_demo import GEM_NOTICES, LICENSE_FILES
import test_cartridge
import test_demo


class Integration:
    def exercise(self, h):
        task_text=h.command('TASKS',b'dos.filesystem')
        require(b'primes' not in task_text.lower(),'PRIMES started automatically')
        require(h.number(h.at('job'))==0,'Unexpected background job')
        h.command('COPY SYS:LONG.TXT WORK:LONG.TXT')
        h.command('CMP SYS:LONG.TXT WORK:LONG.TXT')
        h.command('CD WORK:')
        h.command('DIR',b'LONG.TXT')
        h.command('LIST',b'LONG.TXT')
        baseline=h.ledger()['live']
        service=h.number(h.p['build']['memory']['dos_storage']['SHARED']+68,3)
        previous=h.begin('COPY SYS:LONG.TXT WORK:BREAK.TXT')
        packet=f'dw(${service+39:x})+db(${service+41:x})*65536'
        h.rendezvous(f'(db(${service+453:x})=1)&(dw({packet}+22)=87)')
        started=h.b.eval_expr('@frame')
        h.press('\x03')
        h.ready(previous)
        h.result(304)
        h.cells('copy-break')
        latency=h.b.eval_expr('@frame')-started
        require(h.ledger()['live']==baseline,'COPY BREAK retained a Task')
        h.command('HELLO',b'Hello from disk!')
        h.command('DIR',b'BREAK.TXT')
        h.command('LIST',b'BREAK.TXT')
        h.save_screen(h.p['output']/'boot-smoke.png')
        h.saved['integration']=dict(status='pass',copy_break_frames=latency,
            scope='Physical-key COPY, reopen/CMP, DIR/LIST, BREAK during Write and usable prompt; PRIMES stays loadable and idle.')
        for character in 'EXIT':h.press(character)
        h.b._cmd_ok('KEY RETURN down')
        h.b.bp_clear_all()


def archive(bundle, package, output):
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    require(manifest.get('shell_only') and not manifest.get('desktop'),
            'Use a standard or VBXE shell-only build')
    expected={'Exec-of816.xex',manifest['media'],'altirraos-816.rom',
        'ALTIRRAOS-LICENSE.txt','OF816-LICENSE.txt','README.txt','SHA256SUMS',
        *LICENSE_FILES,*(m['name'] for m in manifest['additional_media']),
        'cartridge/README.txt',
        'cartridge/Exec-of816-atarimax-8mbit.bin',
        'cartridge/Exec-of816-atarimax-8mbit-old.car',
        'cartridge/Exec-of816-atarimax-8mbit-new.car'}
    if manifest.get('bitmap'):expected.update(GEM_NOTICES)
    extracted=output/'extracted'
    extracted.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(package) as z:
        names=z.namelist()
        require(len(names)==len(expected) and set(names)==
            {'exec816-demo/'+name for name in expected},'Unexpected preview ZIP contents')
        contents={name:z.read('exec816-demo/'+name) for name in expected}
    sums={name:digest for digest,name in (line.split('  ',1)
        for line in contents['SHA256SUMS'].decode('ascii').splitlines())}
    require(set(sums)==expected-{'SHA256SUMS'},'Incomplete preview checksums')
    for name,digest in sums.items():
        require(hashlib.sha256(contents[name]).hexdigest()==digest,'Changed archived file: '+name)
    for name in expected:
        path=extracted/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(contents[name])
    for name in ('Exec-of816.xex',manifest['media'],'altirraos-816.rom',
                 *(m['name'] for m in manifest['additional_media'])):
        require(sha256(bundle/'of816'/name)==sums[name],'Archive differs from built bytes: '+name)
    require('PRIMES' in manifest['commands'],'Missing loadable PRIMES')
    return extracted,dict(sha256=sha256(package),checksums=sums)


def run(bundle, package_build, output, variant, route):
    output.mkdir(parents=True,exist_ok=True)
    extracted,package=archive(bundle,package_build/'exec816-demo.zip',output)
    if route=='xex':
        shell=test_demo.run(bundle,boot_smoke=True,distribution_root=extracted,
                            integration=Integration())
        boot=dict(autoboot_frames=shell['autoboot_frames'])
    else:
        cart=test_cartridge.run(package_build/'cartridge-build/Exec-of816',bundle,
            ROOT,output/'cartridge',variant,False,integration=Integration(),
            distribution_root=extracted)
        shell=cart['shell'];boot=cart
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    source=Audit((extracted/manifest['media']).read_bytes());source.sdfs()
    work=shell['work_media'][0]
    work_path=(output/'cartridge/demo' if route=='cartridge' else bundle)/work['name']
    audit=Audit(work_path.read_bytes());allocation=audit.sdfs()
    require(audit.files['LONG.TXT']==source.files['LONG.TXT'],'COPY persisted bytes differ')
    prefix=audit.files['BREAK.TXT']
    require(0<len(prefix)<len(source.files['LONG.TXT']) and
        source.files['LONG.TXT'].startswith(prefix),'BREAK persisted an incorrect prefix')
    record=dict(status='pass',tier='development',route=route,variant=variant,
        package=package,boot=boot,shell=shell,allocation=allocation,
        copied_bytes=len(audit.files['LONG.TXT']),break_prefix_bytes=len(prefix),
        observer_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=0),
        scope='Exact archived bytes; selected XEX or cartridge route, not a full release matrix.')
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--package-build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--variant',choices=('old','new'),required=True)
    p.add_argument('--route',choices=('xex','cartridge'),required=True)
    args=p.parse_args()
    run(args.bundle.resolve(),args.package_build.resolve(),args.output.resolve(),
        args.variant,args.route)
    print('Packaged COPY and BREAK passed:',args.route,args.variant,flush=True)
