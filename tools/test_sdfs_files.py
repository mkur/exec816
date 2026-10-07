#!/usr/bin/env python3
"""Execute the native SDFS parser against immutable, independently read-back media.

The guest sector provider uses a deduplicated byte store, without parsing maps.
Its addresses are merely ATR physical-sector offsets. This avoids per-sector
host handshakes and fits the complete fixture in the existing upper-RAM image.
"""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from make_sdfs_fixtures import Media

def provider(raw):
    media=Media(raw);table=bytearray(2001*4);packed=bytearray();seen={}
    for sector in range(1,2001):
        at=media.at(sector);payload=bytes(raw[at:at+(128 if sector<=3 else media.size)])
        if payload not in seen:seen[payload]=0xb2000+len(packed);packed+=payload
        struct.pack_into('<I',table,sector*4,seen[payload])
    require(0xb2000+len(packed)<0xef000,'Fixture exceeds upper-memory provider arena')
    return [(0xb0000,bytes(table)),(0xb2000,bytes(packed))]

def run(t,out,mode,size):
    source=ROOT/f'tests/fixtures/sdfs/sdfs-21-{size}.atr';raw=source.read_bytes();media=Media(raw);root=media.word(25)
    def start(name):return int.from_bytes(media.row(media.entry(root,name))[1:3],'little')
    large=start('LARGE.BIN');sparse=start('SPARSE.BIN')
    def count(start):
        maps,data=media.chain(start);return len(maps)+sum(bool(s) for s in data)
    config=struct.pack('<9H',size,root,start('BINARY.BIN'),large,sparse,start('EMPTY'),count(large),count(sparse),count(start('BINARY.BIN')))
    p=build(t,ROOT/'tests/programs/sdfs_files.act',out,optimize=mode=='opt',tasks=True,console=False,dos_mounts=[],
        image_data=[(0xa0000,bytes(514)),(0xa0800,config),*provider(raw)])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('SDFS checks',data(b,p['image'],'checks',True),'phase',data(b,p['image'],'phase'),flush=True)
            for item in p['image']['data']:
                if item['name'].startswith('M_SDFSTEST') and any('_'+n+'_' in item['name'] for n in ('WORK','FILE','OPERATION')):
                    print(item['name'],b.memdump(item['address'],item['size']).hex(' '),flush=True)
            raise
        ownership(b,p,out);require(data(b,p['image'],'finished')==[1],'SDFS fixture incomplete')
        observations={name:data(b,p['image'],name,True) for name in ('checks','dataReads','mapReads','cacheBytes','stateBytes')}
    return dict(status='pass',mode=mode,sector_bytes=size,build=p['build'],runtime=runtime,machine=machine,observations=observations,fixture_sha256=sha256(source),provider_sha256=sha256(Path(__file__)),scope='Native parser, memory sector provider; no SIO timing claim')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--size',type=int,choices=(128,256),required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(compiler(ROOT/'build/actionc'),out,args.case,args.size)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDFS files passed',args.case,args.size,flush=True)
