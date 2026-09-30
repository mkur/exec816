#!/usr/bin/env python3
"""Execute relative DOS paths from independent non-shell Tasks."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data


def relative(t,out,mode,bank=1,size=128):
    out.mkdir(parents=True,exist_ok=True)
    names=bytearray(1024)
    paths=('D1:','D1:TOOLS','SUB/DATA.BIN','DATA.BIN','','TOOLS/SUB/DATA.BIN','TOOLS/SUB',
           'D1:TOOLS/SUB','/','/TOOLS/SUB','///',':TOOLS/SUB',':','SUB','..','MISSING','D2:TOOLS/SUB')
    for index,path in enumerate(paths):
        raw=path.encode();names[index*32:index*32+len(raw)]=raw
    media=[]
    for index in range(2):
        path=out/f'volume{index}.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',path)
        if index==1:
            from mydos_fixtures import Image
            disk=Image(path.read_bytes())
            manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
            volume=next(v for v in manifest['volumes'] if v['sector_bytes']==size)
            target=next(f for f in volume['files'] if f['path']=='TOOLS/SUB/DATA.BIN')
            for sector in target['chain']:
                at=disk.offset(sector);used=disk.data[at+size-1]
                for byte in range(used):disk.data[at+byte]^=16
            path.write_bytes(disk.data)
        media.append((path,sha256(path)))
    mounts=[dict(alias=f'D{index+1}',unit=49+index,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1) for index in range(2)]
    p=build(t,ROOT/'tests/programs/dos_relative_paths.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,
            kernel_bank=bank,console=False,dos_mounts=mounts,
            image_data=[(0xd1000,bytes(names)),(0xd3000,bytes(256)),(0xd3200,bytes(260)),(0xd4000,bytes(800))])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.config('diskemu','fastest')
        for index,(path,digest) in enumerate(media):b.mount(index,str(path.resolve()))
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Relative checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        require(data(b,p['image'],'finished')==[1],'Incomplete relative fixture')
        require(all(sha256(path)==digest for path,digest in media),'Read-only media modified')
        observations=dict(checks=data(b,p['image'],'checks',True))
    return dict(status='pass',mode=mode,bank=bank,sector_bytes=size,build=p['build'],runtime=runtime,
                machine=machine,observations=observations,media=[digest for path,digest in media],
                media_variant='D2 DATA.BIN payload XOR16; D1 remains original; independent reads expect seeds67/83.')

def bounds(t,out,mode,corrupt=False):
    import struct
    from mydos_fixtures import Image
    from test_dos_lock_names import headless
    out.mkdir(parents=True,exist_ok=True)
    original=(ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes();disk=Image(original)
    def entry(start,name=b'ABCDEFGHXYZ',flags=16,count=8):return bytes([flags])+struct.pack('<HH',count,start)+name
    at=disk.offset(361);disk.data[at:at+16]=entry(500)
    for sector in range(500,636):
        at=disk.offset(sector);disk.data[at:at+128]=bytes(128)
    if corrupt:
        at=disk.offset(500)
        disk.data[at:at+16]=entry(500,b'SELF       ')
        disk.data[at+16:at+32]=entry(504,b'OVERLAP    ')
        disk.data[at+32:at+48]=entry(500,b'BAD     BIN',0x42,1)
        alias='D1';paths=[alias+':ABCDEFGH.XYZ','SELF','OVERLAP','BAD.BIN']
    else:
        for index in range(16):
            at=disk.offset(500+index*8);disk.data[at:at+16]=entry(508+index*8)
            if index==15:disk.data[at+16:at+32]=entry(0,b'PAYLOAD_BIN',0x42,0)
        alias='ABCDEFGHIJKLMNOPQRSTUVWXYABCDEF';deep=alias+':'+('/'.join(['ABCDEFGH.XYZ']*16))
        paths=[deep,'ABCDEFGH.XYZ','/','//ABCDEFGH.XYZ/ABCDEFGH.XYZ','/ABCDEFGH.XYZ/PAYLOAD_.BIN','',deep.rsplit('/',1)[0]]
    blob=bytearray(2048)
    for index,path in enumerate(paths):blob[index*256:index*256+len(path)]=path.encode()
    fixture=out/'dos_relative_bounds.act'
    fixture.write_text((ROOT/'tests/programs/dos_relative_bounds.act').read_text().replace('BYTE finished,variant','BYTE finished\nCONST variant='+str(int(corrupt))))
    # Reserve both output buffers explicitly in the image map.
    return headless(t,out,mode,fixture.resolve(),bytes(blob),[bytes(disk.data)],
        [dict(alias=alias,unit=49,sectors=720,sector_bytes=128,profile=1)],extra_data=[(0xe0200,bytes(260))],corrupt=corrupt,
        original_media_sha256=sha256(ROOT/'tests/fixtures/mydos/mydos450-128.atr'),fixture_sha256=sha256(fixture))


def large(t,out,mode):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-256.atr',media)
    digest=sha256(media);names=b'LARGE.BIN\0'.ljust(32,b'\0')+b'D1:\0'
    p=build(t,ROOT/'tests/programs/dos_relative_large.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,
        console=False,dos_mounts=[dict(alias='D1',unit=49,sectors=2000,sector_bytes=256,profile=1)],image_data=[(0xd1000,names)])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media.resolve()))
        try:runtime,_=execute(b,p,timeout=600,frame_limit=30000)
        except Exception:
            print('Relative large-read checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        observations={n:int.from_bytes(bytes(data(b,p['image'],n)),'little') for n in ('checks','received','verified','ioError')}
        require(observations==dict(checks=10,received=70003,verified=70003,ioError=0),'Incomplete relative large Read')
        require(sha256(media)==digest,'Read-only media changed')
    return dict(status='pass',mode=mode,build=p['build'],runtime=runtime,machine=machine,observations=observations,media_sha256=digest)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--only');parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--output',type=Path,default=ROOT/'build/dos-relative')
    a=parser.parse_args();t=compiler(a.compiler_dir)
    from test_dos_abi import run as abi
    from test_dos_streams import nil,fixture
    from test_dos_lifetime import run as lifetime
    from test_dos_directories import run as directories
    cases=[]
    for bank in (1,3):
        for size in (128,256):cases.append((f'bank{bank}-{size}',lambda out,bank=bank,size=size:relative(t,out,a.case,bank,size)))
    cases += [('depth',lambda out:bounds(t,out,a.case)),('corrupt-ancestry',lambda out:bounds(t,out,a.case,True)),
              ('abi',lambda out:abi(t,out,a.case=='opt')),('headless',lambda out:nil(t,out,a.case)),
              ('mixed',lambda out:nil(t,out,a.case,True)),('lifetime',lambda out:lifetime(t,out,a.case)),
              ('directories',lambda out:directories(t,out,a.case,128)),
              ('relative-large',lambda out:large(t,out,a.case)),
              ('absolute-large',lambda out:fixture(t,out,a.case,'dos_large_read.act',large=True))]
    for name,action in cases:
        if a.only and name not in a.only.split(','):continue
        out=a.output/a.case/name;out.mkdir(parents=True,exist_ok=True)
        print('Running relative paths',a.case,name,flush=True)
        r=action(out);r['name']=name
        (out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Relative paths passed',a.case,flush=True)

if __name__=='__main__':main()
