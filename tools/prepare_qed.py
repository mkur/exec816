#!/usr/bin/env python3
"""Restore checked QED/cflib inputs and prepare a separate native work copy."""
import argparse,hashlib,json,re,shutil,struct,subprocess,urllib.request
from pathlib import Path
from native_program import ROOT,command,require,sha256

PORT=ROOT/'ports/gem4xe/apps/qed'
CACHE=ROOT/'build/qed-sources'


def prepare(output,cache=CACHE):
    output=Path(output).resolve();cache=Path(cache).resolve()
    require(output!=cache and cache not in output.parents and output not in cache.parents,
            'QED work and upstream cache must be separate trees')
    pin=json.loads((PORT/'inputs.json').read_text())
    sources={}
    for item in pin['sources']:
        original=cache/item['id'];work=output/'source'/item['id']
        if (original/'.git').exists():
            require(command(['git','-C',original,'rev-parse','HEAD']).strip()==item['revision'],
                    'Wrong QED source revision: '+item['id'])
            require(command(['git','-C',original,'rev-parse','HEAD^{tree}']).strip()==item['tree'],
                    'Wrong QED source tree: '+item['id'])
        for name,digest in item['files'].items():
            source=original/name
            if not source.exists():
                url=item['repository'].removesuffix('.git').replace('github.com','raw.githubusercontent.com')
                with urllib.request.urlopen(url+'/'+item['revision']+'/'+name,timeout=30) as response:
                    payload=response.read()
                require(hashlib.sha256(payload).hexdigest()==digest,'Changed QED download: '+name)
                source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(payload)
            require(sha256(source)==digest,'Changed QED source: '+item['id']+'/'+name)
        if work.exists():shutil.rmtree(work)
        for name in item['files']:
            target=work/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((original/name).read_bytes())
        sources[item['id']]=dict(revision=item['revision'],tree=item['tree'],files=item['files'])
    patches=sorted((PORT/'patches').glob('*.patch'))
    for patch in patches:command(['patch','-p1','-F','0','-t','-i',patch],cwd=output/'source')
    record=dict(schema_version=1,sources=sources,patches={p.name:sha256(p) for p in patches},
        native_inputs={str(p.relative_to(ROOT)):sha256(p) for p in sorted((PORT/'native').rglob('*')) if p.is_file()},
        exec_inputs={name:sha256(ROOT/name) for name in pin['exec_baseline']['input_files']},
        native_input_changes={name:dict(baseline=digest,current=sha256(ROOT/name))
            for name,digest in pin['exec_baseline']['input_files'].items() if sha256(ROOT/name)!=digest},
        source_manifest_sha256=sha256(PORT/'inputs.json'))
    output.mkdir(parents=True,exist_ok=True)
    (output/'sources.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def inventory(output,optimize=True):
    """Record every candidate's actual native compiler result, including failures."""
    output=Path(output).resolve();prepare(output)
    pin=json.loads((PORT/'inputs.json').read_text());selection=pin['donor_build_inventory']
    cc=Path(shutil.which('cc65816')).resolve();version=command([cc,'--version']).strip()
    require(version.endswith('version 5.18'),'Unpinned QED C compiler')
    objects=output/'objects';objects.mkdir(exist_ok=True)
    roots={'qed':output/'source/qed/src','cflib':output/'source/cflib'}
    flags=['--code-model=large','--data-model=huge','-O2' if optimize else '-O0',
           '-D_WORD=short','-D_UWORD=unsigned short','-DQED_BANKED_MALLOC=1',
           '-Werror=implicit-function-declaration']
    includes=[ROOT/'c/include',PORT/'native',roots['qed'],roots['cflib']]
    units=[]
    for origin,names in [('qed',selection['qed_translation_units']),
                         ('cflib',selection['cflib_archive_translation_units'])]:
        for name in names:
            source=output/'source'/origin/name
            obj=objects/(origin+'-'+source.stem+'.o');log=obj.with_suffix('.log')
            args=[str(cc),*flags,*(['--char-is-unsigned'] if origin=='qed' else []),
                  *[str(part) for path in includes for part in ('-I',path)],'-c','-o',str(obj),str(source)]
            result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
            log.write_bytes(result.stdout)
            errors=re.findall(r'(?:fatal )?error: ([^\n]+)',result.stdout.decode(errors='replace'))
            undefined=[]
            if result.returncode==0:
                # Read undefined ELF symbols without depending on a host nm build.
                raw=obj.read_bytes();h=struct.unpack_from('<HHIIIIIHHHHHH',raw,16)
                rows=[struct.unpack_from('<IIIIIIIIII',raw,h[5]+n*h[10]) for n in range(h[11])]
                for row in rows:
                    if row[1]!=2:continue
                    strings_row=rows[row[6]];strings=raw[strings_row[4]:strings_row[4]+strings_row[5]]
                    for at in range(row[4],row[4]+row[5],16):
                        symbol,value,size,info,other,section=struct.unpack_from('<IIIBBH',raw,at)
                        if symbol and section==0:undefined.append(strings[symbol:].split(b'\0',1)[0].decode())
            units.append(dict(origin=origin,path=name,status='compiled' if result.returncode==0 else 'pending-adaptation',
                returncode=result.returncode,diagnostics=log.name,diagnostics_sha256=sha256(log),
                errors=errors,undefined_symbols=sorted(set(undefined)),
                object_sha256=sha256(obj) if result.returncode==0 else None,command=args))
    exclusions=[dict(origin='cflib',path=name,status='donor-excluded') for name in selection['cflib_exclusions']]
    references=[dict(origin='qed',path=name,status='donor-reference-only') for name in selection['donor_support_translation_units']]
    report=dict(schema_version=1,scope='Native compilation ledger, not a complete executable or layout proof',
        compiler=dict(path=str(cc),version=version,sha256=sha256(cc)),optimized=optimize,
        units=units,exclusions=exclusions,donor_references=references,
        compiled=sum(u['status']=='compiled' for u in units),pending=sum(u['status']!='compiled' for u in units))
    (output/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inventory',action='store_true')
    args=parser.parse_args()
    record=inventory(args.output) if args.inventory else prepare(args.output)
    if args.inventory:print('QED native candidates:',record['compiled'],'compiled,',record['pending'],'pending adaptation')
