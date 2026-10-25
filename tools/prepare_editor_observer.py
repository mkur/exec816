#!/usr/bin/env python3
"""Build an additive PLUS matrix-key alias without replacing pinned binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from native_program import ROOT,require,sha256


def prepare(output,checkout,build_dir):
    output.mkdir(parents=True,exist_ok=True)
    pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
    inputs=pin['mouse_input']['tooling']['source_sha256']
    for name,digest in inputs.items():
        require(sha256(checkout/name)==digest,'Observer source differs from pinned mouse tooling: '+name)
    path=checkout/'src/AltirraSDL/source/bridge/bridge_commands_write.cpp'
    original=path.read_bytes()
    needle=b'{ "ASTERISK", 0x07 }, { "LESS", 0x36 }, { "GREATER", 0x37 },'
    require(original.count(needle)==1,'Changed native matrix alias table')
    reference=checkout/'src/AltirraSDL/source/input/keyboard_keymap_sdl3.cpp'
    require(b"{ '+', 0x06 }" in reference.read_bytes(),'PLUS is not the pinned physical scan code')
    changed=original.replace(needle,b'{ "PLUS", 0x06 }, '+needle)
    try:
        path.write_bytes(changed)
        subprocess.run(['cmake','--build',str(build_dir),'--target','AltirraBridgeServer','-j','4'],check=True)
        candidates=[p for p in build_dir.rglob('AltirraBridgeServer') if p.is_file()]
        require(len(candidates)==1,'Ambiguous observer binary')
        shutil.copy2(candidates[0],output/'AltirraBridgeServer')
    finally:
        path.write_bytes(original)
    sdk=output/'sdk'
    if not sdk.exists():sdk.symlink_to((ROOT/'build/mouse-bridge/sdk').resolve(),target_is_directory=True)
    record=dict(binary=str((output/'AltirraBridgeServer').resolve()),sha256=sha256(output/'AltirraBridgeServer'),
        scope='Additive PLUS key name maps to existing Atari matrix scan $06; CPU/peripheral timing unchanged',
        base=pin['mouse_input']['tooling'],source_override={str(path.relative_to(checkout)):hashlib.sha256(changed).hexdigest()},
        restored_source_sha256=sha256(path),keymap_sha256=sha256(reference))
    (output/'observer.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--checkout',type=Path,default=ROOT/'build/altirra-irq-fix')
    p.add_argument('--build-dir',type=Path,default=ROOT/'build/altirra-irq-fix/build/latency')
    a=p.parse_args();prepare(a.output.resolve(),a.checkout.resolve(),a.build_dir.resolve())
