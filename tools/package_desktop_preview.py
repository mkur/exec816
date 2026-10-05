#!/usr/bin/env python3
"""Add a separately booted desktop preview to the standard OF816 demo ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def verified(archive):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Damaged demo archive')
        names=z.namelist()
        if len(names)!=len(set(names)):
            raise ValueError('Duplicate demo member')
        files={}
        for name in names:
            path=PurePosixPath(name)
            if path.parts[0]!='exec816-demo' or len(path.parts)!=2 or '..' in path.parts:
                raise ValueError('Expected a flat standalone demo')
            leaf=path.name
            if leaf!='SHA256SUMS' and path.suffix not in ('.xex','.atr','.rom','.txt','.md'):
                raise ValueError('Build intermediate in distribution: '+leaf)
            files[leaf]=z.read(name)
    checksums=files.pop('SHA256SUMS').decode('ascii').splitlines()
    expected={name:digest for digest,name in (line.split('  ',1) for line in checksums)}
    if len(expected)!=len(checksums) or set(expected)!=set(files):
        raise ValueError('Incomplete distribution checksums')
    if any(hashlib.sha256(content).hexdigest()!=expected[name] for name,content in files.items()):
        raise ValueError('Changed distribution content')
    for required in ('Exec-of816.xex','system.atr','altirraos-816.rom','README.txt','OF816-LICENSE.txt'):
        if required not in files:raise ValueError('Missing boot artifact: '+required)
    return files


def package(standard,desktop,output):
    files=verified(standard);preview=verified(desktop)
    if files['altirraos-816.rom']!=preview['altirraos-816.rom']:
        raise ValueError('Desktop and standard ROM differ')
    files['README.txt']+=b'\nOptional desktop preview: see desktop/README.txt. Boot desktop/Exec-of816.xex\nwith desktop/system.atr (D1) and desktop/work.atr (D8). The root boot keeps\nthe five-second OF816 autoboot into the standard shell/prime demo.\n'
    files.update({'desktop/'+name:content for name,content in preview.items()})
    digests={name:hashlib.sha256(content).hexdigest() for name,content in sorted(files.items())}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in digests.items()).encode('ascii')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(files.items()):
            info=zipfile.ZipInfo('exec816-demo/'+name)
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,content)
    return dict(archive=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                bytes=output.stat().st_size,members=digests,default='standard shell/prime, five-second OF816 autoboot',
                optional='desktop/Exec-of816.xex with matching desktop media')

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--standard',type=Path,required=True);a.add_argument('--desktop',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();record=package(args.standard,args.desktop,args.output)
    args.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Desktop preview distribution:',args.output)
