#!/usr/bin/env python3
"""Prepare pinned G4BENCH inputs and Exec adapters outside the donor checkout."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from native_program import ROOT, command, require, sha256

PORT=ROOT/'ports/gem4xe/apps/g4bench'
CACHE=ROOT/'build/g4bench/upstream'


def prepare(output):
    output=Path(output).resolve();source=output/'source'
    pin=json.loads((PORT/'inputs.json').read_text())
    for name,digest in pin['files'].items():
        original=CACHE/name
        if not original.exists():
            url='https://raw.githubusercontent.com/slaapliedje/gem4xe/'+pin['revision']+'/'+name
            with urllib.request.urlopen(url,timeout=30) as response:payload=response.read()
            require(hashlib.sha256(payload).hexdigest()==digest,'Changed G4BENCH download: '+name)
            original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(payload)
        require(sha256(original)==digest,'Changed G4BENCH input: '+name)
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(original.read_bytes())
    patches=sorted((PORT/'patches').glob('*.patch'))
    for patch in patches:command(['patch','-p1','-F','0','-t','-i',patch],cwd=source)
    adapters=[*sorted(PORT.glob('*.c')),*sorted(PORT.glob('*.h'))]
    for path in adapters:(source/'src/apps'/path.name).write_bytes(path.read_bytes())
    record=dict(revision=pin['revision'],inputs=pin['files'],
                patches={p.name:sha256(p) for p in patches},
                adapters={p.name:sha256(p) for p in adapters})
    (output/'g4bench.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
