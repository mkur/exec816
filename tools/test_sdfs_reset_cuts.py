#!/usr/bin/env python3
"""Cold RESET at verified publication boundaries, before guest cleanup or Close."""
import argparse
import json
import shutil
import time
from pathlib import Path

from filesystem_audit import Audit, word
from generate_dos_mounts import encode
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_filesystem_write_edges import entry, bitmap
from test_sdfs_write_buffering import instrument
from test_sio_device import PIN


def inspect(media, baseline, stage, amount, payloads):
    image = Audit(media.read_bytes()).image
    addresses, first, _ = entry(image,'sdfs','BATCH.BIN')
    row = bytes(image.data[a] for a in addresses)
    require(row[0] & 0x80, 'RESET cut lost the incomplete flag')
    length = int.from_bytes(row[3:6],'little')
    require(length == (amount if stage == 'directory' else 0), 'Unexpected published length')
    page = image.sector(first)
    pointers = [word(page,n) for n in range(4,image.size,2) if word(page,n)]
    require(len(pointers) == (payloads if stage in ('map','directory') else 0),
            'Map became reachable before its publication stage')
    recorded = word(image.sector(1),13)
    free = sum(bool(image.data[bitmap(image,'sdfs',s)] & (0x80>>(s & 7)))
               for s in range(image.count+1))
    require((recorded != free) == (stage == 'bitmap'), 'Unexpected bitmap/free-count disagreement')
    # Clear only a host copy of the flag to inspect structure; never repair media.
    image.data[addresses[0]] &= 0x7f
    normalized = Audit(image.data)
    finding = None
    try:
        normalized.sdfs()
    except ValueError as error:
        finding = str(error)
    require((finding is not None) == (stage in ('bitmap','header')),
            f'Unexpected external allocation finding: {finding}')
    for sector, owner in baseline.owners.items():
        if any(owner == name or owner.startswith(name+' ') for name in baseline.files):
            require(image.sector(sector) == baseline.image.sector(sector),
                    'RESET cut changed an unrelated allocation')
    if stage == 'directory':
        require(normalized.files['BATCH.BIN'] == bytes((i & 255)^0x6d for i in range(amount)),
                'Published prefix differs after RESET')
    return dict(stage=stage, published_length=length, map_payloads=len(pointers),
                bitmap_free=free, recorded_free=recorded, incomplete=True,
                external_finding=finding, media_sha256=sha256(media),
                classification={'payload':'unreferenced payload; allocation not published',
                                'bitmap':'allocated leaks and stale free count',
                                'header':'allocated leaks; free count agrees',
                                'map':'map pointers beyond published length',
                                'directory':'complete published prefix; writer incomplete'}[stage])


def run(out):
    size,amount = 256,2000
    payloads = (amount+size-1)//size
    instrument(out)
    probe = out/'sdfsbatchprobe.act'
    source = probe.read_text().replace('USE FSTYPES\n','USE FSTYPES\nUSE HEAPCORE\n')
    source = source.replace('PUBLIC CARD count','PUBLIC CARD cut\nPUBLIC CARD count')
    require(source.count('    count==+1\n') == 1, 'Stale RESET observer')
    source = source.replace('    count==+1\n', '    count==+1\n'
                            '    IF count=cut THEN\n      HEAPCORE.Abort($f910)\n    FI\n')
    probe.write_text(source)
    baseline = Audit((ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr').read_bytes())
    baseline.sdfs()
    mounts = [dict(alias='D1',unit=49,sectors=baseline.image.count,sector_bytes=size,
                   format=2,access='readwrite',profile=4)]
    program = build(compiler(ROOT/'build/actionc'),out/'sdfs_write_buffering.act',out,
                    optimize=True,tasks=True,task_capacity=8,console_deferred=True,
                    dos_mounts=mounts,image_data=[(0x30ffd0,bytes([0xa5])*(amount+64)),
                                                (0xd0000,bytes(768))])
    cuts = {'payload':payloads,'bitmap':payloads+1,'header':payloads+2,
            'map':payloads+3,'directory':payloads+4}
    cases = []
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        b.config('diskemu','generic56k')
        b.config('accuratedisk','false')
        machine = verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        for stage,ordinal in cuts.items():
            print('RESET cut',stage,ordinal,flush=True)
            folder = out/stage
            folder.mkdir(exist_ok=True)
            media = folder/'volume.atr'
            shutil.copyfile(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr',media)
            b.bp_clear_all()
            b.boot(str(program['xex']))
            run_to(b,program['labels']['loader_start'],frame_limit=1800,timeout=180)
            b.bp_set(program['labels']['start'])
            run_to(b,program['labels']['start'])
            b.bp_clear_all()
            b.mount(0,str(media))
            b.memload(program['build']['task_storage']['BASE']+0x900,encode(mounts))
            for fragment,value,width in [('_SDFSBATCHTEST_AMOUNT_',amount,4),
                                         ('_SDFSBATCHPROBE_CUT_',ordinal,2)]:
                at = next(d['address'] for d in program['image']['data'] if fragment in d['name'])
                b.memload(at,value.to_bytes(width,'little'))
            # Abort is intercepted at entry, before finish/heap shutdown runs.
            b.bp_set(program['labels']['heap_fault'])
            run_to(b,program['labels']['heap_fault'],frame_limit=20000,timeout=300)
            view = {**program['image'],'data':[d for d in program['image']['data']
                                             if '_SDFSBATCHPROBE_' in d['name']]}
            require(int.from_bytes(bytes(data(b,view,'count')),'little') == ordinal,
                    'RESET intercepted an unexpected fault')
            require(b.memdump(0x800,2) == b'\xff\xff','Guest cleanup started before RESET')
            b.cold_reset()
            time.sleep(1)
            b._cmd_ok('EJECT drive=0')
            cases.append(inspect(media,baseline,stage,amount,payloads))
            (out/'progress.json').write_text(json.dumps(cases,indent=2)+'\n')
    return dict(status='pass',tier='development',build=program['build'],machine=machine,
                cuts=cases,observer_sha256=sha256(probe),
                scope='Actual emulator cold RESET after verified whole-sector writes; no Close, repair, or sector-tearing claim',
                bank_zero_delta=dict(fixed=0,per_task=0))


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
