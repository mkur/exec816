#!/usr/bin/env python3
"""Verify original MagiC MGVIEW bytes and apply the native source patch."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,command,require,sha256

PORT=ROOT/'ports/magic/mgview'


def prepare(output,patch_path=PORT/'native.patch'):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    pin=json.loads((PORT/'inputs.json').read_text())
    for name,row in pin['files'].items():
        source=PORT/'upstream'/name
        require(sha256(source)==row['sha256'],'Changed original MGVIEW input: '+name)
        if source.suffix in ('.C','.H'):
            text=source.read_text(encoding='latin-1')
            (output/name.lower()).write_text(text if text.endswith('\n') else text+'\n')
    patch=Path(patch_path).resolve()
    command(['patch','-p1','-F','0','-t','-i',patch],cwd=output)
    record=dict(upstream=pin,patch_sha256=sha256(patch),
        native={p.name:sha256(p) for p in sorted((PORT/'native').glob('*')) if p.is_file()})
    (output/'sources.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
