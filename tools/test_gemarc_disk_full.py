#!/usr/bin/env python3
"""Exercise GemARC against an actually exhausted writable SDFS disk."""
import argparse,json,subprocess
from pathlib import Path
from native_program import ROOT,require
from prepare_gemarc import prepare,PORT
from test_c_runtime import fixture
from test_c_process import run as process_run
from filesystem_audit import Audit,word
from mydos_fixtures import Image
from make_data_disk import make


def run(out,reuse=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);prepare(out/'prepared')
    source=out/'prepared/source/src/apps'
    seeded={}
    (out/'media/FILL.DAT').unlink(missing_ok=True)
    def nearly_full(path,filesystem):
        media=out/'media';low,high=0,1440;best=None
        while low<=high:
            blocks=(low+high)//2;size=blocks*256
            (media/'FILL.DAT').write_bytes(bytes(size))
            try:
                make(path,media,binary_names={p.name for p in media.iterdir()},
                    filesystem='sdfs',sector_bytes=256,sectors=1440)
            except subprocess.CalledProcessError:
                high=blocks-1;continue
            image=Image(path.read_bytes());free=word(image.sector(1),13)
            if free>=3:
                best=(bytes(image.data),size,free);low=blocks+1
            else:high=blocks-1
        require(best is not None and 3<=best[2]<=4,'Could not seed nearly-full SDFS')
        path.write_bytes(best[0]);(media/'FILL.DAT').write_bytes(bytes(best[1]))
        Audit(path.read_bytes()).sdfs()
        seeded.update(payload_bytes=best[1],initial_free_sectors=best[2])
    result=process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=[ROOT/'tests/programs/gemarc_disk_full.c',
        source/'arcfile.c',source/'arccodec.c',PORT/'native/io.c',PORT/'native/metadata.c'],
        app_options=dict(includes=[source,PORT/'native'],minimum_stack=2560),
        fixture_source=fixture(out,'abi'),expected_completed=2,native_optimize=True,
        release_compiler=True,task_capacity=12,execution=dict(sectors=1440),loader_failures=False,writable=True,prepare_media=nearly_full)
    audit=Audit((out/'system.atr').read_bytes());allocation=audit.sdfs()
    require(audit.files['FULL.ARC']==b'\x1a\0' and 'FILL.DAT' not in audit.files,
            'Disk-full failure damaged original archive or retained fill file')
    result['disk_full']=dict(actual_backend_exhaustion=True,executions=2,full_attempts=1,seeded=seeded,
        original_preserved=True,allocation=allocation)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true');args=parser.parse_args()
    run(args.output,args.from_build)
