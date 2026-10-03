#!/usr/bin/env python3
"""Run extracted demo bytes with build metadata kept outside the archive."""
import argparse,json,shutil,zipfile
from pathlib import Path
from native_program import ROOT,require,sha256
from package_demo import BITMAP_FILES,GEM_FILES,LICENSE_FILES


def extract(bundle,out):
    archive=bundle/'exec816-demo.zip'
    expected={'Exec-of816.xex','system.atr','altirraos-816.rom','ALTIRRAOS-LICENSE.txt',
        'OF816-LICENSE.txt','README.txt','SHA256SUMS',*LICENSE_FILES}
    expected.update('bitmap-console/'+name for name in BITMAP_FILES)
    if 'graphics' in json.loads((bundle/'demo-manifest.json').read_text()):
        expected.update('gem-vdi/'+name for name in GEM_FILES)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        require(len(names)==len(set(names)) and set(names)=={'exec816-demo/'+n for n in expected},
                'Unexpected archive member or missing boot file/notice')
        z.extractall(out)
    extracted=out/'exec816-demo'
    sums=dict(line.split('  ',1)[::-1] for line in (extracted/'SHA256SUMS').read_text().splitlines())
    require(set(sums)==expected-{'SHA256SUMS'},'Incomplete archive checksums')
    require(all(sha256(extracted/name)==digest for name,digest in sums.items()),'Archive checksum mismatch')
    return extracted,sums


def stage(source,out,xex,disk):
    out.mkdir(parents=True,exist_ok=True)
    record=json.loads((source/'demo-manifest.json').read_text())
    for name in ('build.json','program.a816.json','hosted.lbl','loader.lbl','manifest.bin',*record['artifacts']):
        require(Path(name).name==name,'Nonlocal development artifact')
        shutil.copyfile(source/name,out/name)
    require(sha256(xex)==record['artifacts']['program.xex'] and
            sha256(disk)==record['artifacts'][record['media']],'Extracted image/media differs from development metadata')
    shutil.copyfile(xex,out/'program.xex');shutil.copyfile(disk,out/record['media'])
    if record.get('bitmap'):
        shutil.copyfile(source/record['font_source'],out/'font8x8.c')
        record['font_source']='font8x8.c'
    (out/'demo-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    return out


def run(bundle,out,case):
    out.mkdir(parents=True,exist_ok=True)
    extracted,sums=extract(bundle,out)
    if case=='of816':
        program=stage(bundle,out/'program',bundle/'program.xex',extracted/'system.atr')
        monitor=out/'of816';monitor.mkdir(exist_ok=True)
        record=json.loads((bundle/'of816/of816.json').read_text())
        for name in ('Exec-of816.xex','system.atr','altirraos-816.rom','ALTIRRAOS-LICENSE.txt','OF816-LICENSE.txt'):
            shutil.copyfile(extracted/name,monitor/name)
        record['exec_build']=str(program)
        record['media']['manifest_sha256']=sha256(program/'demo-manifest.json')
        (monitor/'of816.json').write_text(json.dumps(record,indent=2)+'\n')
        from test_of816 import run as check
        result=check(monitor)
    else:
        program=stage(bundle/'bitmap-console/program',out/'program',
            extracted/'bitmap-console/Exec-bitmap-console.xex',extracted/'bitmap-console/system.atr')
        from test_demo import run as check
        result=check(program,editing=case=='editing',disk_failure=case if case in ('wrong','missing') else None)
    report=dict(status='pass',tier='development',case=case,archive_sha256=sha256(bundle/'exec816-demo.zip'),
        members=sums,execution=result,runner_sha256=sha256(Path(__file__)))
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',choices=('walkthrough','editing','wrong','missing','of816'),required=True)
    a=p.parse_args();run(a.bundle.resolve(),a.output.resolve(),a.case)
    print('Extracted demo passed',a.case,flush=True)
