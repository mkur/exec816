#!/usr/bin/env python3
"""Prepare pinned GemARC originals and patched work without changing the donor."""
import argparse,hashlib,json,os,sys,tempfile,urllib.request
from pathlib import Path
from native_program import ROOT,command,require,sha256

PORT=ROOT/'ports/gem4xe/apps/gemarc'
CACHE=ROOT/'build/gemarc/upstream'


def prepare(output,cache=CACHE,donor=None):
    output,cache=Path(output).resolve(),Path(cache).resolve()
    require(output!=cache and cache not in output.parents and output not in cache.parents,
            'GemARC work and original cache must be separate')
    pin=json.loads((PORT/'inputs.json').read_text());source=output/'source'
    candidate=Path(donor) if donor else ROOT.parents[1]/'atari/gem4xe'
    local=(candidate/'.git').exists()
    for name,digest in pin['files'].items():
        original=cache/name
        if not original.exists():
            if local:
                import subprocess
                payload=subprocess.check_output(['git','-C',str(candidate),'show',pin['revision']+':'+name])
            else:
                url=pin['repository'].removesuffix('.git').replace('github.com','raw.githubusercontent.com')
                with urllib.request.urlopen(url+'/'+pin['revision']+'/'+name,timeout=30) as response:payload=response.read()
            require(hashlib.sha256(payload).hexdigest()==digest,'Changed GemARC original: '+name)
            original.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=original.parent,delete=False) as temporary:
                temporary.write(payload);temporary_path=Path(temporary.name)
            os.replace(temporary_path,original)
        require(sha256(original)==digest,'Changed GemARC cache input: '+name)
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(original.read_bytes())
    patches=sorted((PORT/'patches').glob('*.patch'))
    for patch in patches:command(['patch','-p1','-F','0','-t','-i',patch],cwd=source)
    output.mkdir(parents=True,exist_ok=True)
    resource=output/'GEMARC.RSC';header=source/'src/apps/gemarcrsc.h'
    command([sys.executable,source/'tools/gemarcrsc.py',resource,header],
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    record=dict(revision=pin['revision'],manifest_sha256=sha256(PORT/'inputs.json'),inputs=pin['files'],
        patches={p.name:sha256(p) for p in patches},
        outputs={'GEMARC.RSC':sha256(resource),'gemarcrsc.h':sha256(header)},resource_bytes=resource.stat().st_size)
    (output/'gemarc.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--donor',type=Path)
    args=parser.parse_args();prepare(args.output,donor=args.donor)
