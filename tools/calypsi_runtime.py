"""Prepare explicit, pinned corrections to the installed Calypsi C runtime."""
import json
from pathlib import Path
from native_program import ROOT,command,require,sha256

PIN=ROOT/'toolchain/calypsi-runtime.json'
def prepare(output,tool_root):
    pin=json.loads(PIN.read_text());folder=Path(output)/'runtime-source';folder.mkdir(parents=True,exist_ok=True)
    for name,digest in {**pin['sources'],**pin['headers']}.items():
        require(sha256(tool_root/name)==digest,'Changed Calypsi runtime source/header: '+name)
    sources=[]
    for name in pin['sources']:
        path=folder/Path(name).name;path.write_bytes((tool_root/name).read_bytes());sources.append(path)
    for name,digest in pin['patches'].items():
        path=ROOT/name;require(sha256(path)==digest,'Changed Calypsi runtime correction: '+name)
        command(['patch','-p1','-F','0','-t','-i',path],cwd=folder)
    return sources,tool_root/'src/lib',dict(manifest_sha256=sha256(PIN),
        original_sources=pin['sources'],headers=pin['headers'],patches=pin['patches'],
        prepared_sources={str(p):sha256(p) for p in sources})
