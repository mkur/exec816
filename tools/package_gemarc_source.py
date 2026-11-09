#!/usr/bin/env python3
"""Package corresponding GemARC/Exec sources separately from the boot ZIP."""
import argparse,gzip,io,json,shutil,subprocess,tarfile
from pathlib import Path
from native_program import ROOT,require,sha256
from prepare_gemarc import CACHE


def package(application,output,revision):
    application=application.resolve();output=output.resolve()
    require(not output.exists(),'Use a fresh GemARC source output')
    app=json.loads((application/'app.json').read_text())
    require(sha256(application/'program.app')==app['sha256'],'Changed GemARC APP')
    revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',revision],text=True).strip()
    output.mkdir(parents=True);tree=output/'material';tree.mkdir()
    archive=subprocess.check_output(['git','-C',str(ROOT),'archive','--format=tar',revision])
    exec_source=tree/'exec816';exec_source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:source.extractall(exec_source,filter='data')
    (exec_source/'exec816-demo.zip').unlink(missing_ok=True)
    for name,digest in {**app['inputs'],**app['c_runtime']['inputs']}.items():
        source=Path(name)
        if source.is_relative_to(ROOT) and not source.is_relative_to(ROOT/'build'):
            require(sha256(exec_source/source.relative_to(ROOT))==digest,'Source revision differs: '+name)
    shutil.copytree(application/'source',tree/'source')
    shutil.copytree(application/'runtime-source',tree/'runtime-source')
    pin=json.loads((exec_source/'ports/gem4xe/apps/gemarc/inputs.json').read_text())
    for name,digest in pin['files'].items():
        require(sha256(CACHE/name)==digest,'Changed GemARC original: '+name)
        target=exec_source/'build/gemarc/upstream'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(CACHE/name,target)
    for name in ('gemarc.json','app.json','GEMARC.RSC','runtime-main.c'):
        shutil.copyfile(application/name,tree/name)
    (tree/'README.txt').write_text(
        'GemARC corresponding sources for Exec816\n\n'
        'The matching APP hash and import ABI are in app.json. Donor revision,\n'
        'resource and patch hashes are in gemarc.json. Original pinned inputs\n'
        'are seeded in exec816/build/gemarc/upstream; source/ is the patched tree.\n'
        'Exec source includes public bindings, common runtime, native platform,\n'
        'build scripts, tests and notices. runtime-source/ retains adapted\n'
        'Calypsi sources and notices. Calypsi 5.18 is required separately.\n\n'
        'From exec816 run:\n'
        '  python3 tools/build_gemarc.py --output build/gemarc/rebuilt\n'
        'See exec816/docs/contributing/building.md for provider/demo builds.\n'
        'The application and donor patches retain GPL-2.0-or-later; Exec and\n'
        'runtime files keep the terms in their notices and LICENSING.md.\n')
    record=dict(tier='development',source_revision=revision,app_sha256=app['sha256'],
        abi=app['abi']['version'],files={p.relative_to(tree).as_posix():sha256(p)
            for p in sorted(tree.rglob('*')) if p.is_file()})
    (tree/'source-material.json').write_text(json.dumps(record,indent=2)+'\n')
    target=output/('exec816-gemarc-'+revision[:12]+'-source.tar.gz')
    with target.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for path in sorted(tree.rglob('*')):
                if not path.is_file():continue
                info=archive.gettarinfo(str(path),arcname='gemarc-source/'+path.relative_to(tree).as_posix())
                info.uid=info.gid=info.mtime=0;info.uname=info.gname=''
                with path.open('rb') as source:archive.addfile(info,source)
    result=dict(status='pass',source_revision=revision,app_sha256=app['sha256'],
        archive=str(target),sha256=sha256(target))
    (output/'source-results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--revision',default='HEAD');args=parser.parse_args()
    package(args.application,args.output,args.revision)
