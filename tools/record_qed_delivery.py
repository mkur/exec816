#!/usr/bin/env python3
"""Record supported development delivery only after every concrete gate passes."""
import argparse
import hashlib
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path

from filesystem_audit import Audit
from native_program import ROOT, require, sha256
from package_demo import LICENSE_FILES, GEM_NOTICES, CALCULATOR_NOTICES, G4BENCH_NOTICES, QED_NOTICES
from qed_delivery import PORT, read, checked, require_distribution
from qed_demo import verify
from relink_qed import material
from check_qed_reproduction import RUNTIME

GATES=('qd1','qd2','qd3','qd4','qd5','qd6')
FINAL_CASES={'shell-save-as-backup-reopen','files-document-launch','quit-cancel-keeps-document',
             'quit-save-continuation','discard','normal-parent-collection'}


def grants(policy):
    expected={'qed','cflib','native','bindings','runtime'}
    require(set(policy.get('grants',{}))==expected and all(policy['grants'].values()),
            'Incomplete QED component grants')
    decision=policy.get('grant_decisions',{}).get('native-adapter-grant',{})
    require(decision.get('status')=='authorized' and decision.get('license')=='MIT' and
            decision.get('authority') and decision.get('files'), 'Missing explicit native adapter grant')
    expected_files={str(p.relative_to(ROOT)) for p in (PORT/'native').glob('*')
                    if p.suffix in ('.c','.h') and p.name!='qed-gem-extra.h'}
    require(set(decision['files'])==expected_files,'Native adapter grant scope differs')
    for name,digest in decision['files'].items():
        checked(ROOT/name,digest)
        require('SPDX-License-Identifier: MIT' in (ROOT/name).read_text().splitlines()[0],
                'Native adapter grant notice missing: '+name)
    checked(ROOT/'LICENSING.md',decision['notice_sha256'])


def passed_execution(path,bundle,app_sha):
    result=read(path);runtime=result.get('runtime',{})
    require(result.get('status')=='pass' and result.get('tier')=='development' and
        runtime.get('status')==0 and runtime.get('guards')=='intact' and runtime.get('live_tasks')==0 and
        runtime.get('native_nmi_count',0)>0 and runtime.get('native_irq_count',0)>0 and
        runtime.get('switching')==0 and runtime.get('os_busy')==0 and
        249<=result.get('autoboot_frames',0)<=251 and result.get('integration',{}).get('normal_collection'),
        'Incomplete QED delivery execution: '+str(path))
    require(result.get('zip_sha256')==sha256(bundle/'exec816-demo.zip') and
        result.get('production_app_sha256')==app_sha and
        result.get('boot_xex_sha256')==sha256(bundle/'of816/Exec-of816.xex') and
        result.get('media_sha256')==sha256(bundle/'system.atr') and
        not result.get('diagnostic_media_sha256') and not result.get('companion_overrides') and not result.get('omitted_media'),'Final execution differs from the healthy candidate')
    require(result.get('observer_inputs'),'Missing final QED observer inputs')
    for name,digest in result['observer_inputs'].items():checked(ROOT/name,digest)
    return result


def archive(bundle):
    expected={'Exec-of816.xex','system.atr','work.atr','qed.atr','altirraos-816.rom','ALTIRRAOS-LICENSE.txt',
        'OF816-LICENSE.txt','README.txt','SHA256SUMS',*LICENSE_FILES,*GEM_NOTICES,
        *CALCULATOR_NOTICES,*G4BENCH_NOTICES,*QED_NOTICES}
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as packed:
        names=packed.namelist()
        require(len(names)==len(set(names)) and set(names)=={'exec816-demo/'+n for n in expected},
                'Unexpected or missing QED ZIP member')
        sums=packed.read('exec816-demo/SHA256SUMS').decode().splitlines()
        rows=[line.split('  ',1) for line in sums]
        require(len(rows)==len(expected)-1 and {n for _,n in rows}==expected-{'SHA256SUMS'},
                'Incomplete QED ZIP checksums')
        for digest,name in rows:
            require(hashlib.sha256(packed.read('exec816-demo/'+name)).hexdigest()==digest,'Changed QED ZIP member: '+name)
        for name,source in LICENSE_FILES.items():
            require(packed.read('exec816-demo/'+name)==(ROOT/source).read_bytes(),'Stale packaged licence: '+name)
        for name in ('system.atr','work.atr','qed.atr'):
            require(packed.read('exec816-demo/'+name)==(bundle/name).read_bytes(),'Stale packaged media: '+name)
        require(packed.read('exec816-demo/Exec-of816.xex')==(bundle/'of816/Exec-of816.xex').read_bytes(),
                'Stale packaged OF816 XEX')
    return sorted(expected)


def source_companion(path,expected,zip_sha,app_sha):
    checked(path,expected)
    with tempfile.TemporaryDirectory(prefix='qed-source-audit-') as temporary:
        root=Path(temporary)
        with tarfile.open(path) as packed:
            require(not any(p.name.endswith(('clib-lc-hd.a','cc65816','as65816','ln65816')) for p in packed),
                    'Compiler/SDK archive escaped into source companion')
            packed.extractall(root,filter='data')
        record=material(root/'qed-source-relink')
        require(record['zip_sha256']==zip_sha and record['app_sha256']==app_sha and
                not record['unresolved'],'Stale/unresolved source companion')
        require(record['native_source_identity']['revision']==record['source_revision'] and
                not record['native_source_identity']['dirty'],'Source companion is not the final frozen native source')
        return dict(sha256=expected,source_revision=record['source_revision'],files=len(record['files']))


def reproduced(path,bundle):
    record=read(path)
    require(record.get('status')=='pass' and record.get('clean_checkout') and len(record.get('builds',[]))==2 and
        set(record.get('runtime_files',{}))==set(RUNTIME) and
        len(set(record['builds']))==2 and record.get('zip_sha256')==sha256(bundle/'exec816-demo.zip'),
        'Incomplete QED reproducibility evidence')
    for directory in record['builds']:
        for name,digest in record['runtime_files'].items():checked(Path(directory)/name,digest)
    for name,digest in record['runtime_files'].items():checked(bundle/name,digest)
    return record


def gate_identities(gates,manifest):
    """Historical checks keep their scope, but must describe this APP/provider."""
    records={name:read(path) for name,path in gates.items()}
    current=manifest['qed'];app=current['app_sha256'];provider=current['provider_identity']
    resource=current['resource_sha256']
    for name in ('qd1','qd2'):
        row=records[name]['qed'] if name=='qd2' else records[name]
        require((row.get('app_sha256'),row.get('provider_identity'),row.get('resource_sha256'))==
                (app,provider,resource),'Stale QED gate identity: '+name)
    for name in ('qd4','qd5'):
        require(records[name].get('production_app_sha256')==app,'Stale QED gate APP: '+name)
    require(records['qd5'].get('provider_identity')==provider,'Stale QD5 provider')
    row=records['qd6']
    require((row.get('app_sha256'),row.get('provider_identity'),row.get('resource_sha256'))==
            (app,provider,resource) and row.get('source_revision')==manifest['kernel']['exec_build']['revision'],
            'Stale QD6 frozen candidate')
    return records


def record(bundle,gates,final,source,source_sha,repro):
    policy=read(PORT/'delivery.json');require_distribution(policy);grants(policy)
    require(set(gates)==set(GATES),'Incomplete QED delivery gates')
    for name,path in gates.items():require(read(path).get('status')=='pass','Failed QED gate: '+name)
    manifest=read(bundle/'demo-manifest.json');verify(manifest,bundle);members=archive(bundle)
    gate_identities(gates,manifest)
    app=manifest['qed']['app_sha256'];executed=passed_execution(final,bundle,app)
    require(FINAL_CASES<=set(executed['integration'].get('cases',[])) and
        executed['integration'].get('parents')==['shell','desktop'], 'Incomplete final parent/workflow cases')
    # The final independent allocation/byte gate reads the closed test disk itself.
    disk=Path(final).parent/'work-walkthrough.atr';oracle=Audit(disk.read_bytes());allocation=oracle.sdfs()
    require(oracle.files.get('FINAL.TXT')==b'cab' and oracle.files.get('FINAL.BAK')==b'ab',
            'Final persisted document/backup differs')
    companion=source_companion(source,source_sha,sha256(bundle/'exec816-demo.zip'),app)
    reproduction=reproduced(repro,bundle)
    require(companion['source_revision']==reproduction['source_revision']==manifest['kernel']['exec_build']['revision'],
            'Source/reproduction/native revisions differ')
    return dict(schema_version=1,status='pass',tier='development',qualification=False,
        distribution_ready=True,unresolved=[],requirements=policy['requirements'],deferrals=policy['deferrals'],
        bundle=str(bundle),zip_sha256=sha256(bundle/'exec816-demo.zip'),members=members,
        app_sha256=app,resource_sha256=manifest['qed']['resource_sha256'],provider_identity=manifest['qed']['provider_identity'],
        gates={n:dict(path=str(p),sha256=sha256(p)) for n,p in gates.items()},
        final_execution=dict(path=str(final),sha256=sha256(final)),source_companion=companion,
        reproducibility=dict(path=str(repro),sha256=sha256(repro)),allocation=allocation,
        bank_zero_delta=dict(fixed=0,per_public_task=0,private_idle=0),
        recorder_sha256=sha256(Path(__file__)),release='Separate full qualification, matching cartridges and publication remain')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    for name in GATES:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--final',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--repro',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=record(a.bundle.resolve(),{n:getattr(a,n) for n in GATES},a.final,a.source,a.source_sha256,a.repro)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
