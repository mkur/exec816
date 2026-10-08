#!/usr/bin/env python3
"""Reproduce the pinned calculator sources and flat resource outside the donor."""
import argparse,hashlib,json,os,sys,urllib.request
from pathlib import Path
from native_program import ROOT,command,require,sha256

PORT=ROOT/'ports/gem4xe/apps/calculator'
CACHE=ROOT/'build/calculator/upstream'


def prepare(output,cache=CACHE):
    output=Path(output).resolve();source=output/'source'
    pin=json.loads((PORT/'inputs.json').read_text())
    for name,digest in pin['files'].items():
        original=cache/name
        if not original.exists():
            url='https://raw.githubusercontent.com/slaapliedje/gem4xe/'+pin['revision']+'/'+name
            with urllib.request.urlopen(url,timeout=30) as response:payload=response.read()
            require(hashlib.sha256(payload).hexdigest()==digest,'Changed calculator download: '+name)
            original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(payload)
        require(sha256(original)==digest,'Changed calculator input: '+name)
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(original.read_bytes())
    patches=sorted((PORT/'patches').glob('*.patch'))
    for patch in patches:command(['patch','-p1','-F','0','-t','-i',patch],cwd=source)
    (source/'src/apps/calculator.h').write_bytes((PORT/'calculator.h').read_bytes())
    resource=output/'CALC.RSC';header=source/'src/apps/calcrsc.h'
    command([sys.executable,source/'tools/calcrsc.py',resource,header],
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    record=dict(revision=pin['revision'],inputs=pin['files'],
                patches={p.name:sha256(p) for p in patches},
                outputs={'CALC.RSC':sha256(resource),'calcrsc.h':sha256(header)},
                resource_bytes=resource.stat().st_size,
                adapter_inputs={'calculator.h':sha256(PORT/'calculator.h')})
    (output/'calculator.json').write_text(json.dumps(record,indent=2)+'\n')
    return record



def resource_cases(output):
    """Small resource-admission corpus, derived from the shipped flat tree."""
    import struct
    output=Path(output);prepare(output)
    raw=(output/'CALC.RSC').read_bytes()
    objects,ted=struct.unpack_from('>HH',raw,2)
    cases={}
    def case(name):
        data=bytearray(raw);cases[name]=data;return data
    data=case('TEDBAD.RSC');struct.pack_into('>I',data,objects+2*24+12,ted+1)
    data=case('TEDSHORT.RSC');struct.pack_into('>H',data,4,len(raw)-8)
    data=case('TEDSTR.RSC');struct.pack_into('>I',data,ted,len(raw)-2);data[-2:]=b'AB'
    data=case('SHARED.RSC');struct.pack_into('>H',data,objects+24+6,21)
    struct.pack_into('>I',data,objects+24+12,ted)
    return {'CALC.RSC':raw,**{name:bytes(data) for name,data in cases.items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();prepare(args.output)

