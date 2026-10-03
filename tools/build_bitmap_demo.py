#!/usr/bin/env python3
"""Build the shared shell/prime session against a matching demo system disk."""
import argparse,json,shutil
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT,require,sha256


def build(output,media_bundle,optimize=True):
    output=Path(output).resolve();media_bundle=Path(media_bundle).resolve()
    media=json.loads((media_bundle/'demo-manifest.json').read_text())
    disk=media_bundle/media['media']
    require(sha256(disk)==media['artifacts'][media['media']],'Changed matching system disk')
    p=build_bitmap(ROOT/'examples/demo.act',output,optimize=optimize,
        dos_mounts=media['mounts'],system_mount=media['kernel']['system_mount'])
    out=p['output'];shutil.copyfile(disk,out/'system.atr')
    pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
    record=dict(format='exec816-bitmap-demo-v1',bitmap=True,tier='development',pin=pin,
        kernel=p['build'],configuration={**pin['configuration'],'diskemu':'generic56k'},
        media='system.atr',filesystem=media['filesystem'],mounts=media['mounts'],files=media['files'],
        font_source='../selected/src/vdi/font8x8.c',
        artifacts={name:sha256(out/name) for name in ('program.xex','system.atr')},
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in [ROOT/'examples/demo.act',ROOT/'examples/demo-session.inc',ROOT/'config/kernel.json',Path(__file__)]},
        media_manifest_sha256=sha256(media_bundle/'demo-manifest.json'))
    (out/'demo-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    return p

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--media-bundle',type=Path,required=True);a.add_argument('--raw',action='store_true');args=a.parse_args()
    print(build(args.output,args.media_bundle,not args.raw)['xex'])
