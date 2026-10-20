#!/usr/bin/env python3
"""Record completed FastBasic FP development checks without qualifying a release."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from build_fastbasic import ROOT, PIN, ABI, sha256
from native_program import require

CASES = {
    'runtime_compiler': 'build/fastbasic/fp-all-final/results.json',
    'integer_regression': 'build/fastbasic/fp-integer-regression/results.json',
    'decimal_raw': 'build/fastbasic/fp-raw-final/results.json',
    'decimal_optimized': 'build/fastbasic/fp-opt-final/results.json',
    'numeric_edges': 'build/fastbasic/fp-edges-final/results.json',
    'source_capacity': 'build/fastbasic/fp-capacity/results.json',
    'lifetime': 'build/fastbasic/fp-lifetime-final/results.json',
    'native_return_nmi': 'build/fastbasic/fp-lifetime-nmi/results.json',
    'save_faults': 'build/fastbasic/fp-faults-final/results.json',
    'original_controls': 'build/fastbasic/fp-controls/results.json',
    'original_rom_control': 'build/fastbasic/fp-rom-control/results.json',
    'source_rebuild': 'build/fastbasic-fp-source-check/results.json',
    'refresh_rejection': 'build/fastbasic/fp-refresh-reject.json',
    'refresh_matching': 'build/fastbasic/fp-refresh-match.json',
    'text_package': 'build/fastbasic-fp-demo/text/fastbasic-checks.json',
    'graphical_package': 'build/fastbasic-fp-demo/graphical/fastbasic-checks.json',
}


def record(output):
    records, evidence = {}, {}
    for name, path in CASES.items():
        data = json.loads((ROOT/path).read_text())
        require(data['status'] == 'pass', 'Incomplete FastBasic evidence: '+name)
        records[name] = data
        evidence[name] = dict(path=path, sha256=sha256(ROOT/path))
        for key in ('checks','scope','return_probe','breakTicks','source_capacity',
                    'source_base','capacity_results','reused_native_fixture'):
            if key in data:
                evidence[name][key] = data[key]
    for key, optimized in (('decimal_raw',False),('decimal_optimized',True)):
        require(records[key]['decimal_probe'] and records[key]['optimize']==optimized,
                'Missing actual decimal interruption probe: '+key)
    require(records['numeric_edges']['corpus'][0]['numeric_snapshot_probe'],
            'Fixed RND endpoints must identify their test-only input override')
    require(records['native_return_nmi']['return_probe']==7,'Missing forced native-return NMI')
    for key in ('lifetime','native_return_nmi'):
        require(records[key]['breakTicks']<=2,'Unbounded math-heavy BREAK')
    build=json.loads((ROOT/'build/fastbasic/build.json').read_text())
    for name, data in build['compilers'].items():
        require(sha256(ROOT/f'build/fastbasic/{name}.COM')==data['sha256'],
                'Changed final compiler: '+name)
        require(records['source_rebuild']['compilers'][name]==data['sha256'],
                'Clean source build differs: '+name)
    host=ROOT/'build/fastbasic/fp-host-tests.log'
    text=host.read_text().replace('\r\n','\n')
    count=re.search(r'Ran (\d+) tests',text)
    require(count and text.rstrip().endswith('OK'),'Host suite did not pass')
    native=json.loads((ROOT/'build/fastbasic-fp-demo/text/program.a816.json').read_text())
    modules=('FBSTATE','FBPROGRAM','FBFILES','FBSERVICE','FBBIND')
    code={name:sum(r['size'] for r in native['routines']
                  if r['name'].startswith('M_'+name+'_')) for name in modules}
    packages={}
    for variant in ('text','graphical'):
        path=f'build/fastbasic-fp-demo/{variant}/exec816-demo.zip'
        packages[variant]=dict(path=path,sha256=sha256(ROOT/path))
    inputs={str(p.relative_to(ROOT)):sha256(p) for p in (
        ROOT/'abi/fastbasic.json', ROOT/'toolchain/actionc.json',
        *sorted((ROOT/'lib/dos').glob('fb*.act')),
        *sorted(p for p in (ROOT/'ports/fastbasic').rglob('*') if p.is_file()),
        *sorted((ROOT/'tools').glob('*fastbasic*.py')),
        ROOT/'tools/shell_session_walkthrough.py')}
    result=dict(format='exec816-fastbasic-floating-point-development-v1',
        status='pass',tier='development',qualification=False,
        source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        working_tree='Implementation inputs are hashed per build and below; preceding commit is not the working-tree identity',
        source_inputs=inputs,upstream=PIN,abi=ABI,compilers=build['compilers'],
        evidence=evidence,host_tests=dict(path=str(host.relative_to(ROOT)),sha256=sha256(host),tests=int(count[1])),
        memory=dict(bank_zero_delta=dict(baseline='Enabled SDX/integer profile',
            fixed=0,root_kernel=0,per_public_task=0,idle=0,
            includes='guards, alignment and unused capacity'),
            shared_guarded_direct_pages=544,aligned_bank_reservation_per_image=131072,
            session_bytes=records['runtime_compiler']['session_bytes'],
            image_record_bytes=72,native_module_code_bytes=code,
            private_fp_stack_bytes=48,private_math_pointer_bytes=15,snapshot_bytes=4,
            note='FP state uses existing guest-bank/D capacity. File snapshots add allocator-rounded upper bytes.'),
        packages=packages,source_archive='build/fastbasic-fp-demo/exec816-fastbasic-source.zip',
        source_archive_checksum='External .zip.sha256 sidecar avoids a self-referential hash in the source archive',
        remaining=['General guest IRQ/NMI and hosted-system release qualification',
            'Physical hardware qualification',
            'Uniform numeric accuracy bounds outside the recorded corpus',
            'Exhaustive parser/output cancellation and pointer/focus timing matrices',
            'Integrated editor (FB7), hardware statements and external user USR'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/development/fastbasic-floating-point.json')
    args=parser.parse_args()
    record(args.output.resolve())
    print('FastBasic FP development evidence recorded')
