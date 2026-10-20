#!/usr/bin/env python3
"""Reconcile executed QED foundation artifacts against one current source/ABI baseline."""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
from analysis_artifact import reject_analysis
from c_program import ABI
from native_program import ROOT,read_build,require,sha256
from qed_stack_observer import markers,summarize


def checked(path,digest):
    require(path.is_file() and sha256(path)==digest,'Changed evidence input: '+str(path))


def check(layout_directory,cohort_directories,demo_directories,frames_path=None):
    layout=json.loads((layout_directory/'layout.json').read_text())
    require(layout['complete_link'] and layout['status']=='analysis-only' and layout['abi']==ABI,
            'Incomplete or stale complete-source layout')
    checked(layout_directory/'program.elf',layout['analysis_elf_sha256'])
    for name,digest in layout['build_inputs'].items():checked(Path(name),digest)
    frames_path=frames_path or layout_directory/'stack-frames.json'
    frames=json.loads(frames_path.read_text())
    require(frames['analysis_sha256']==sha256(layout_directory/'layout.json') and
            frames['source_chain_bytes']+frames['continuation_cap_bytes']+
            frames['interrupt_reserve_bytes']+frames['required_headroom_bytes']<=frames['admission_bytes'],
            'Stale or excessive source stack ledger')
    canonical=layout_directory/'inputs/source'
    cohorts=[];inputs={}
    for directory in cohort_directories:
        result=json.loads((directory/'results.json').read_text())
        require(result['status']=='pass' and result['app']['abi']==ABI,'Failed/stale cohort: '+str(directory))
        program=read_build(directory/'program');build=program['build']
        provider=build['foreign_image']['c_program_provider']
        require(provider['abi']==ABI['version'] and provider['imports']==ABI['imports'],'Provider ABI differs')
        require(result['runtime']['native_nmi_count']>0 and result['runtime']['native_irq_count']>0,
                'Missing native asynchronous entries')
        checked(directory/'app/program.app',result['app']['sha256'])
        checked(directory/'program/program.a816.json',build['image_sha256'])
        checked(program['xex'],build['xex_sha256'])
        for group in ('platform_inputs','task_inputs','console_inputs','banked_inputs'):
            for name,digest in build.get(group,{}).items():
                checked(ROOT/name,digest);inputs[name]=digest
        for name,digest in result['app']['inputs'].items():
            path=Path(name);checked(path,digest)
            if '/inputs/source/' in name:
                path=canonical/name.split('/inputs/source/',1)[1]
                checked(path,digest)
            inputs[str(path)]=digest
        provenance=result['app']['image']['provenance']
        for tool in provenance['tools'].values():checked(Path(tool['path']),tool['sha256'])
        checked(Path(provenance['runtime']['path']),provenance['runtime']['sha256'])
        observed=summarize(directory/'emulator.log',markers(program,result['app']),build['memory'],result.get('stack_window'))
        current_min=min(r['headroom'] for r in observed['minima'] if r['lifetime'] and r['kind']!='async')
        original_min=min(r['headroom'] for r in result['stacks']['minima'] if r['lifetime'] and r['kind']!='async')
        require(current_min==original_min,'Changed stack interpretation: '+str(directory))
        cohorts.append(dict(reanalysis_sha256=sha256(ROOT/'tools/qed_stack_observer.py'),path=str(directory.relative_to(ROOT)),results_sha256=sha256(directory/'results.json'),
            app_sha256=result['app']['sha256'],completed=result['completed'],checks=result['checks'],
            filesystem=result['filesystem'],stack_window=result.get('stack_window'),
            minimum_headroom=current_min,
            trace_sha256=sha256(directory/'emulator.log')))
    demos=[]
    for directory in demo_directories:
        manifest=json.loads((directory/'demo-manifest.json').read_text())
        for name,digest in manifest['artifacts'].items():checked(directory/name,digest)
        path=directory/'exec816-demo.zip'
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            require((directory/'of816/Exec-of816.xex').is_file() and
                    all('exec816-demo/'+n in names for n in ['Exec-of816.xex','OF816-LICENSE.txt',
                        'altirraos-816.rom','ALTIRRAOS-LICENSE.txt','SHA256SUMS']),
                    'Demo omitted OF816, matching ROM or notices')
            require(not any(n.lower().endswith(('.elf','.json','.lst','.o','.log')) for n in names),
                    'Development artifacts escaped into distribution')
            for name in names:
                if not name.endswith('/'):reject_analysis(archive.read(name))
            for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
                digest,name=line.split(None,1)
                require(hashlib.sha256(archive.read('exec816-demo/'+name.strip().lstrip('*'))).hexdigest()==digest,
                        'Invalid packaged checksum: '+name)
            require(hashlib.sha256(archive.read('exec816-demo/altirraos-816.rom')).hexdigest()==
                    manifest['pin']['rom']['sha256'],'Unpinned packaged ROM')
        row=dict(path=str(directory.relative_to(ROOT)),zip_sha256=sha256(path),files=names)
        if manifest.get('gem_desktop'):
            provider=json.loads((directory/'bitmap-console/c-image.json').read_text())
            contract=provider['provenance']['c_program_provider']
            require(contract['abi']==ABI['version'] and contract['imports']==ABI['imports'],'Stale packaged provider')
            code=sum(len(s['bytes']) for s in provider['segments'] if s['executable'])
            tables=sum(len(s['bytes']) for s in provider['segments'] if s['address']>>16 in provider['provenance']['readonly_table_banks'])
            data=sum(len(s['bytes']) for s in provider['segments'] if s['writable'])+sum(s['size'] for s in provider['zero_fill'])
            caps=layout['selection']['resident_provider_allowances']
            require(code+caps['code_bytes']<=3*65536 and tables+caps['table_bytes']<=65536
                    and data+caps['data_bss_bytes']<=65536,'Packaged provider exceeds future allowance')
            from filesystem_audit import Audit
            audit=Audit((directory/'system.atr').read_bytes());getattr(audit,manifest['filesystem'])()
            apps=[]
            for name,raw in audit.files.items():
                if raw[:4]!=b'C816':continue
                require(struct.unpack_from('<H',raw,6)[0]==ABI['version'],'Stale packaged APP: '+name)
                reject_analysis(raw);apps.append(name)
            require(apps,'No packaged C callers rebuilt')
            rebuilt=[]
            native=read_build(directory)['build']['gem_applications']
            for profile in (directory/'bitmap-console/apps').glob('*/app.json'):
                app=json.loads(profile.read_text())
                require(app['abi']==ABI,'Stale C caller profile: '+str(profile))
                checked(profile.parent/'program.app',app['sha256'])
                require(native[profile.parent.name]['sha256']==app['sha256'],
                        'C caller differs from native boot manifest')
                rebuilt.append(profile.parent.name)
            row.update(provider_sha256=sha256(directory/'bitmap-console/c-image.json'),
                provider_code_bytes=code,provider_table_bytes=tables,provider_data_bss_bytes=data,apps=apps,rebuilt_callers=rebuilt)
        demos.append(row)
    return dict(status='pass',tier='development',qualification=False,abi=ABI['version'],
        process_abi=json.loads((ROOT/'abi/process.json').read_text())['version'],
        layout_sha256=sha256(layout_directory/'layout.json'),frames_sha256=sha256(frames_path),
        auditor_sha256=sha256(Path(__file__)),source_pins=layout['inputs']['sources'],
        verified_source_inputs=inputs,cohorts=cohorts,demos=demos)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout',type=Path,required=True)
    parser.add_argument('--frames',type=Path)
    parser.add_argument('--cohort',type=Path,action='append',default=[])
    parser.add_argument('--demo',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record=check(args.layout.resolve(),[p.resolve() for p in args.cohort],[p.resolve() for p in args.demo],args.frames)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('QED baseline reconciled:',len(record['cohorts']),'cohorts,',len(record['demos']),'packages')
