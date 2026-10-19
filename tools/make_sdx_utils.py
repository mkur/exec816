#!/usr/bin/env python3
"""Make a writable utility disk from verified, unmodified SDX inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from native_program import ROOT, require, sha256
from sdx_patch import manifests, select
from sdfs_reference import make, extract
from test_sdx_arc import archive


def build(out,inputs):
    out.mkdir(parents=True,exist_ok=True)
    source=out/'source';source.mkdir(exist_ok=True)
    catalog=manifests(ROOT/'compat/sdx')
    for directory,names in [('md5',['MD5.COM']),('arc',['ARC.COM','ARCLST.OVL','ARCEXT.OVL','ARCADD.OVL']),('edx',['EDX.COM'])]:
        for name in names:
            raw=(inputs/directory/name).read_bytes()
            _,module=select(raw,catalog)
            require(module['file']==name,'Wrong pinned utility: '+name)
            (source/name).write_bytes(raw)
    for directory,name in [('md5','MD5.MAN'),('edx','EDX.MAN')]:
        shutil.copyfile(inputs/directory/name,source/name)
    (source/'ABC.TXT').write_bytes(b'abc')
    (source/'BINARY.BIN').write_bytes(bytes(range(256)))
    (source/'EDIT.TXT').write_bytes(b'HELLO\x9bSECOND LINE\x9b')
    (source/'CHECK.MD5').write_bytes(b''.join(hashlib.md5((source/name).read_bytes()).hexdigest().encode()+b'  '+name.encode()+b'\x9b' for name in ('ABC.TXT','BINARY.BIN')))
    (source/'SAMPLE.ARC').write_bytes(archive({'EXTRACT.TXT':b'ARC extraction works through Exec816 SDX.\x9b','EMPTY.TXT':b''}))
    (source/'README.TXT').write_bytes(b'''Exec816 SDX utilities\x9bMount this disk at D2 with FORMAT SPARTA READWRITE.\x9bUse a demo built with --sdx --sdx-drive-a D2: --sdx-car-root D2:.\x9bD2:MD5 ABC.TXT\x9bD2:MD5 /C CHECK.MD5\x9bD2:ARC\x9bD2:ARC L SAMPLE.ARC\x9bD2:EDX EDIT.TXT\x9bEDX: Ctrl-Z end of line; type; Ctrl-S save; Return confirms; Esc exits.\x9bFiles use ATASCII EOL ($9B). A: and CAR: map to the build's fixed root.\x9bOnly pinned binaries are supported. EDX bell and live resize are unsupported.\x9b''')
    make(out/'sdx-utils.atr',source,2880,256,'SDXUTILS')
    (out/'sdx-utils.atr.sha256').write_text(sha256(out/'sdx-utils.atr')+'  sdx-utils.atr\n')
    readback=out/'readback';extract(out/'sdx-utils.atr',readback)
    expected={p.name:dict(bytes=p.stat().st_size,sha256=sha256(p)) for p in source.iterdir() if p.is_file()}
    require(expected=={p.name:dict(bytes=p.stat().st_size,sha256=sha256(p)) for p in readback.iterdir() if p.is_file()},'Utility disk readback differs')
    (out/'utils-manifest.json').write_text(json.dumps(dict(files=expected,disk_sha256=sha256(out/'sdx-utils.atr')),indent=2)+'\n')
    return out/'sdx-utils.atr'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,default=ROOT/'build/sdx-inputs')
    args=parser.parse_args();print(build(args.output.resolve(),args.inputs.resolve()))
