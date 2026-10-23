#!/usr/bin/env python3
"""Prepare checked QED source/relink materials alongside the small boot ZIP."""
import argparse
import gzip
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

from native_program import ROOT, require, sha256
from qed_demo import verify
from qed_delivery import read, PORT, inventory
from relink_qed import material, COMPONENTS


def build(bundle,output,revision,compiler_dir=None):
    bundle,output=bundle.resolve(),output.resolve()
    require(not output.exists(),'Use a fresh source-material output')
    demo=read(bundle/'demo-manifest.json');verify(demo,bundle)
    production=Path(demo['qed']['production_layout']).parent
    layout=read(production/'layout.json');app=read(production/'app.json')
    provenance=layout['image']['provenance'];output.mkdir(parents=True)
    tree=output/'material';tree.mkdir()
    # Git supplies corresponding Exec source; runtime inputs must match this tree.
    revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',revision],text=True).strip()
    archive=subprocess.check_output(['git','-C',str(ROOT),'archive','--format=tar',revision])
    exec_source=tree/'exec816';exec_source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:source.extractall(exec_source,filter='data')
    for group in ('platform_inputs','task_inputs','console_inputs','banked_inputs'):
        for name,digest in demo['kernel'].get(group,{}).items():
            require(sha256(exec_source/name)==digest,'Source revision differs from runtime input: '+name)
    # Delivery helpers are supplied source additions, individually bound below.
    for name in ('relink_qed.py','package_qed_source.py'):
        shutil.copyfile(ROOT/'tools'/name,exec_source/'tools'/name)
    shutil.copytree(production/'inputs/source',tree/'source')
    shutil.copytree(PORT/'native',tree/'native')
    shutil.copytree(PORT/'patches',tree/'patches')
    shutil.copytree(production/'runtime-source',tree/'runtime-source')
    shutil.copytree(production/'inputs/resource',tree/'resource')
    third=tree/'third-party';third.mkdir()
    for name in ('selected','aes-selected'):
        shutil.copytree(bundle/'bitmap-console'/name,third/('gem-'+name))
    for name in ('calc','g4bench'):
        shutil.copytree(bundle/'bitmap-console/apps'/name/'source',third/name)
    # Only linked target support and its notices; no compiler/SDK executables.
    compiler_directory=(compiler_dir or ROOT/'build/actionc').resolve()
    compiler_revision=subprocess.check_output(['git','-C',str(compiler_directory),'rev-parse','HEAD'],text=True).strip()
    require(compiler_revision==demo['kernel']['revision'] and not subprocess.check_output(
        ['git','-C',str(compiler_directory),'status','--porcelain']),'Compiler source differs from native build')
    for name,digest in demo['kernel']['memory_runtime_inputs'].items():
        require(sha256(compiler_directory/'runtime/65816'/name)==digest,'Compiler runtime source differs: '+name)
    shutil.copytree(compiler_directory/'runtime/65816',third/'actionc-runtime')
    shutil.copytree(compiler_directory/'docs/abi',third/'actionc-abi')
    for name in ('LICENSE','LICENSE-MIT','COPYING'):
        if (compiler_directory/name).is_file():shutil.copyfile(compiler_directory/name,third/('actionc-'+name))
    objects=[];mapping={};inputs=list(app['inputs'])
    for index,name in enumerate(provenance['link_objects']):
        source=Path(name);target='objects/'+source.name
        (tree/'objects').mkdir(exist_ok=True);shutil.copyfile(source,tree/target);objects.append(target)
        if index<len(inputs) and '/source/cflib/' in inputs[index]:
            mapping[target]='source/cflib/'+Path(inputs[index]).name
    policy=read(PORT/'delivery.json')
    linked=inventory(production,bundle/'bitmap-console/c-image.json')
    (tree/'link-inventory.json').write_text(json.dumps(linked,indent=2)+'\n')
    application_sources={}
    for name,digest in app['inputs'].items():
        if '/inputs/source/' in name:target='source/'+name.split('/inputs/source/',1)[1]
        elif '/apps/qed/native/' in name:target='native/'+Path(name).name
        else:target='exec816/'+Path(name).relative_to(ROOT).as_posix()
        require(sha256(tree/target)==digest,'Prepared corresponding source differs: '+target)
        application_sources[target]=digest
    for name,digest in provenance['runtime_source_overrides']['prepared_sources'].items():
        target='runtime-source/'+Path(name).name
        require(sha256(tree/target)==digest,'Prepared runtime correction differs')
        application_sources[target]=digest
    (tree/'README.txt').write_text(
        'Exec816 QED source and relink materials\n\n'
        'Install Calypsi 5.18 separately; its compiler/runtime archive is not included.\n'
        'The exact tool and archive hashes are in source-material.json. Python 3 and\n'
        'the ordinary documented Exec build prerequisites are required.\n\n'
        'Relink unchanged application/library objects:\n'
        'python3 exec816/tools/relink_qed.py --material . --output relinked\n\n'
        'Modify a CF-Lib source, then replace its mapped object:\n'
        'python3 exec816/tools/relink_qed.py --material . --output modified \\\n'
        '  --replace-cflib objects/NUMBER-name.o path/to/modified.c\n'
        'source-material.json maps every supplied CF-Lib object to its source.\n'
        'The relinker checks every supplied file and independently verifies relocation\n'
        'in all admitted banks. A replacement APP is a separate diagnostic artifact.\n\n'
        'For a source rebuild use exec816/docs/guides/qed-exec.md and the pinned\n'
        'inputs/ordered patches under exec816/ports/gem4xe/apps/qed/.\n'
        'resource/ includes the generated English resource and its ledger.\n'
        'source/cflib/COPYING.LIB, source/qed/dist/liesmich.txt, the donor notices,\n'
        'runtime-source/ notices and exec816/LICENSING.md retain their own terms.\n'
        'QED redistribution must be free of charge.\n\n'
        'Unresolved delivery questions: '+(', '.join(policy['unresolved']) or 'none')+'\n')
    files={p.relative_to(tree).as_posix():sha256(p) for p in sorted(tree.rglob('*')) if p.is_file()}
    record=dict(schema_version=1,abi=layout['abi'],source_revision=revision,
        app_sha256=demo['qed']['app_sha256'],zip_sha256=sha256(bundle/'exec816-demo.zip'),
        minimum_stack_bytes=layout['selection']['minimum_stack_bytes'],
        tools=provenance['tools'],runtime_sha256=provenance['runtime']['sha256'],
        compiler_options=layout['selection']['compiler_options'],objects=objects,cflib_objects=mapping,
        unresolved=policy['unresolved'],distribution_ready=False,
        components=list(COMPONENTS),
        component_sources={c:[n for n in files if n.startswith(prefix) and Path(n).suffix in ('.c','.h','.s','.act','.inc')]
                           for c,prefix in COMPONENTS.items()},
        grants=policy['grants'],application_sources=application_sources,
        native_source_identity=demo['kernel']['exec_build'],compiler_source_revision=compiler_revision,files=files)
    (tree/'source-material.json').write_text(json.dumps(record,indent=2)+'\n');material(tree)
    destination=output/('exec816-qed-'+revision[:12]+'-source-relink.tar.gz')
    with destination.open('wb') as stream,gzip.GzipFile(filename='',fileobj=stream,mode='wb',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for path in sorted(tree.rglob('*')):
                if not path.is_file():continue
                info=archive.gettarinfo(str(path),arcname='qed-source-relink/'+path.relative_to(tree).as_posix())
                info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
                with path.open('rb') as source:archive.addfile(info,source)
    (output/'QED-DELIVERY-SHA256SUMS').write_text(
        sha256(bundle/'exec816-demo.zip')+'  exec816-demo.zip\n'+sha256(destination)+'  '+destination.name+'\n')
    result=dict(status='prepared',tier='development',qualification=False,unresolved=policy['unresolved'],
        archive=str(destination),sha256=sha256(destination),source_material_sha256=sha256(tree/'source-material.json'),
        source_revision=revision,zip_sha256=record['zip_sha256'])
    (output/'source-results.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    a=p.parse_args();build(a.bundle,a.output,a.revision,a.compiler_dir)
