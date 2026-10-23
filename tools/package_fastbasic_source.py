#!/usr/bin/env python3
"""Package this Exec tree and verified FastBasic corresponding source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from build_fastbasic import ROOT, prepare, sha256, verify_files


def package(output, build_dir=ROOT/'build/fastbasic'):
    directory, _, source, identities=prepare(build_dir)
    expected=json.loads((directory/'port-source.json').read_text())
    verify_files(source,expected)
    files={'fastbasic/'+name:(source/name).read_bytes() for name in expected}
    names=subprocess.check_output(['git','ls-files','--cached','--others',
                                   '--exclude-standard','-z'],cwd=ROOT).split(b'\0')
    for raw in names:
        if not raw:continue
        if raw==b'exec816-demo.zip':continue  # Separate binary distribution.
        name=raw.decode()
        path=ROOT/name
        if path.is_file():files['exec816/'+name]=path.read_bytes()
    files['README.txt']=('Exec816 / FastBasic corresponding source\n\n'
        'fastbasic/ is the complete pinned donor tree with the Exec patch and\n'
        'target already applied, including bundled cc65 and mini65 sources.\n'
        'exec816/ is the current working source snapshot, including native\n'
        'adapters, pins, patch, examples and build instructions.\n\n'
        'See exec816/ports/fastbasic/README.md to rebuild FB.COM, FBI.COM,\n'
        'FBCI.COM, FBC.COM and BASIC.APP.\n'
        'See exec816/docs/contributing/building.md for the native system.\n'
        'No build intermediates are included. Preserve all donor notices.\n').encode()
    files['fastbasic-inputs.json']=(json.dumps(identities,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(f'{hashlib.sha256(raw).hexdigest()}  {name}\n'
                              for name,raw in sorted(files.items())).encode()
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(files.items()):
            member=zipfile.ZipInfo(name)
            member.compress_type=zipfile.ZIP_DEFLATED
            member.external_attr=0o100644<<16
            archive.writestr(member,raw)
    output.with_suffix(output.suffix+'.sha256').write_text(sha256(output)+'  '+output.name+'\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(package(args.output))
