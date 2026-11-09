#!/usr/bin/env python3
"""Focused raw/optimized C binding execution and independent persisted metadata."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from test_c_runtime import fixture
from test_c_process import run as process_run
from filesystem_audit import Audit
from mydos_fixtures import Image
from test_filesystem_write_edges import entry


def run(out,mode):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/c_file_date.c'
    # The two-cycle ABI fixture creates fresh Images and uses the same native
    # optimized bridge in either C mode.
    result=process_run(out,mode=='opt',app_sources=[source],fixture_source=fixture(out,'abi'),
        expected_completed=2,native_optimize=True,release_compiler=True,loader_failures=False,writable=True)
    audit=Audit((out/'system.atr').read_bytes());audit.sdfs()
    require(audit.files.get('DATE.DAT')==b'date','Persisted file bytes differ')
    image=Image((out/'system.atr').read_bytes())
    positions,_,_=entry(image,'sdfs','DATE.DAT')
    timestamp=bytes(image.data[at] for at in positions[17:23])
    require(timestamp==bytes([29,2,24,23,59,58]),'Independent on-disk timestamp differs')
    result['c_file_date']=dict(mode=mode,days=16860,minutes=1439,ticks=2900,
        persisted_timestamp_hex=timestamp.hex(),wide_pointer_rejections=2)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['raw','opt'],default='opt');args=parser.parse_args();run(args.output,args.case)
