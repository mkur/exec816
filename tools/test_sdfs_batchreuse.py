#!/usr/bin/env python3
"""Alternate settled Writes across files/mounts and independently audit both media."""
import argparse
import json
import shutil
import time
from pathlib import Path

from filesystem_audit import Audit
from generate_dos_mounts import encode
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(out):
    media, baselines, mounts = [], [], []
    for index, size in enumerate((128, 256)):
        path = out/f'volume-{size}.atr'
        shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/sdfs-{size}.atr', path)
        audit = Audit(path.read_bytes())
        audit.sdfs()
        media.append(path)
        baselines.append(audit)
        mounts.append(dict(alias=f'D{index+1}', unit=49+index, sectors=audit.image.count,
                           sector_bytes=size, format=2, access='readwrite', profile=4))
    program = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/sdfs_batchreuse.act',
                    out, optimize=True, tasks=True, task_capacity=8,
                    console_deferred=True, dos_mounts=mounts,
                    image_data=[(0x30ffd0, bytes([0xa5])*(1500+64))])
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        b.config('diskemu','generic56k')
        b.config('accuratedisk','false')
        machine = verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            for index,path in enumerate(media):
                b.mount(index,str(path))
            b.memload(program['build']['task_storage']['BASE']+0x900,encode(mounts))
        runtime,_ = execute(b,program,before_run=before,timeout=600,frame_limit=30000)
        ownership(b,program,out)
        raw = b.memdump(0x30ffd0,1500+64)
        require(raw[:32] == raw[-32:] == bytes([0xa5])*32,'Caller buffer guards changed')
        time.sleep(3)
        for index in range(2):
            b._cmd_ok(f'EJECT drive={index}')
    records = []
    for index,path in enumerate(media):
        after = Audit(path.read_bytes())
        allocation = after.sdfs()
        length,seed,name = (1500,0x61,'BATCHA.BIN') if index == 0 else (1300,0x72,'BATCHB.BIN')
        payload = bytes((i & 255)^seed for i in range(length))
        if index == 0:
            payload += bytes(i^0x83 for i in range(17))
        require(after.files == {**baselines[index].files,name:payload},'Workspace reuse changed bytes')
        records.append(dict(image=path.name,sha256=sha256(path),allocation=allocation))
    return dict(status='pass',tier='development',build=program['build'],runtime=runtime,
                machine=machine,media=records,bank_zero_delta=dict(fixed=0,per_task=0))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out)
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
