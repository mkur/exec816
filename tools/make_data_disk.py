#!/usr/bin/env python3
"""Build read-only shell/demo data media; SDFS is the new bundle default."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from native_program import ROOT,sha256
import sdfs_reference
from make_shell_disk import make as mydos

def make(path,source=ROOT/'examples/shell-disk',binary_names=(),sector_bytes=128,filesystem='sdfs',sectors=720):
    path=Path(path);source=Path(source);binary_names=set(binary_names)
    if filesystem=='mydos':return mydos(path,source,binary_names,sector_bytes,sectors)
    if filesystem!='sdfs' or sector_bytes not in (128,256) or not 368<=sectors<=65535:
        raise ValueError('Unsupported playground filesystem/geometry')
    expected={}
    with tempfile.TemporaryDirectory() as temp:
        staging=Path(temp)/'source';staging.mkdir()
        for item in sorted(source.rglob('*')):
            relative=item.relative_to(source);target=staging/relative
            for component in relative.parts:
                base,_,suffix=component.partition('.')
                if not (1<=len(base)<=8 and len(suffix)<=3 and base[0] not in '0123456789' and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in base+suffix)):
                    raise ValueError('Expected supported uppercase 8.3 name: '+str(relative))
            if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            data=item.read_bytes() if relative.as_posix() in binary_names else item.read_text(encoding='ascii').encode('ascii')
            expected[relative.as_posix()]=data;target.write_bytes(data)
        path.parent.mkdir(parents=True,exist_ok=True)
        sdfs_reference.make(path,staging,sectors,sector_bytes)
        hashes=sdfs_reference.verify(path,expected,Path(temp)/'verified')
    proof=dict(schema_version=1,filesystem='SDFS 2.1',sector_bytes=sector_bytes,sectors=sectors,media_sha256=sha256(path),
        producer_sha256=sha256(sdfs_reference.reference()),reference_sources=sdfs_reference.FILES,
        verification='Independent Altirra filesystem validation and complete byte-for-byte extraction',files=hashes)
    path.with_suffix('.verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    return expected
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source',type=Path,default=ROOT/'examples/shell-disk');parser.add_argument('--format',choices=('sdfs','mydos'),default='sdfs');parser.add_argument('--sector-bytes',type=int,choices=(128,256),default=128);parser.add_argument('--sectors',type=int,default=720);args=parser.parse_args()
    files=make(args.output,args.source,sector_bytes=args.sector_bytes,filesystem=args.format,sectors=args.sectors)
    print(f'{args.output}: {args.format.upper()}, {args.sectors} x {args.sector_bytes}, {len(files)} files')
