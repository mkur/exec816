"""Native discovery/protection and independently checked writes on production APT."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,build,execute,require
from make_data_disk import make
from build_ide_media import write
from ideplus_media import put_sector
from test_ideplus import ide_emulator
from test_heap_api import clean_ownership
from test_cooperative import data

def run(out):
    out.mkdir(parents=True,exist_ok=True);(out/'source').mkdir(exist_ok=True)
    (out/'source/README.TXT').write_text('IDE-only partition\n')
    make(out/'stage.atr',out/'source',sector_bytes=512,sectors=1440)
    record=write(out/'ideplus.img',out/'stage.atr',out/'stage.atr')
    before=(out/'ideplus.img').read_bytes()
    p=build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ide_only_media.act',out,
            optimize=True,tasks=True,task_capacity=8,sio_enabled=False)
    with ide_emulator(out,out/'ideplus.img',writable=True) as b:
        runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
    expected=bytearray(before);m=record['partitions'][1]
    put_sector(expected,m['start'],1400,bytes((i&255)^0xa7 for i in range(512)))
    require((out/'ideplus.img').read_bytes()==expected,'Unexpected media/metadata/neighbour mutation')
    (out/'results.json').write_text(json.dumps(dict(status='pass',tier='development',mapping=record,
        runtime=runtime,checks=checks,build=p['build']),indent=2)+'\n')
    print('IDE-only APT discovery and persisted writes passed',flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id3');v=a.parse_args();run(v.output)
