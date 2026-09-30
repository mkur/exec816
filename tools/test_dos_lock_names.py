#!/usr/bin/env python3
"""Native canonical lock names and variable-sized lock ownership."""
from library_paths import read_source
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data


def names(t,out,mode,bank=1):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    digest=sha256(media);paths=bytearray(512)
    for offset,path in ((0,b'd1:'),(32,b'd1:tOoLs/sUb'),(64,b'd1:tools/sub/data.bin'),(96,b'd1:case.txt'),
                        (256,b'D1:'),(288,b'D1:TOOLS/SUB'),(320,b'D1:TOOLS/SUB/DATA.BIN'),(352,b'D1:case.txt'),(384,b'RAW:'),(416,b'NIL:')):
        paths[offset:offset+len(path)]=path
    p=build(t,ROOT/'tests/programs/dos_lock_names.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,
            kernel_bank=bank,console=True,dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],
            image_data=[(0xd1000,bytes(paths)),(0xcffe0,bytes([165])*288),(0xe0000,bytes(16)),(0xbff80,bytes([165])*400)])
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items(): b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.config('diskemu','fastest');b.mount(0,str(media))
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Lock-name checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        require(data(b,p['image'],'finished')==[1],'Incomplete lock-name fixture')
        from banked_test_memory import read
        require(read(b,0xcffe0,16,out)==bytes([165])*16 and read(b,0xd00f0,16,out)==bytes([165])*16,'Name buffer guards')
        require(read(b,0xbff80,16,out)==bytes([165])*16 and read(b,0xc00f4,16,out)==bytes([165])*16,'Lock trailer guards')
        require(sha256(media)==digest,'Read-only media changed')
        values=data(b,p['image'],'layouts',True)
        observed=dict(checks=data(b,p['image'],'checks',True),layouts=values)
    return dict(status='pass',mode=mode,build=p['build'],runtime=runtime,machine=machine,observations=observed,media_sha256=digest)

def allocation(t,out,mode):
    out.mkdir(parents=True,exist_ok=True)
    module=read_source(ROOT/'lib/fs/fslocks.act').replace('USE EXEC','USE EXEC\nUSE DOSFAULTCONTROL',1)
    original='  LET item=FSTYPES.LockObject POINTER(EXEC.AllocMem('
    require(module.count(original)==1,'Stale allocation probe')
    module=module.replace(original,'  IF DOSFAULTCONTROL.failNext<>0 THEN DOSFAULTCONTROL.failNext=0 RETURN(NULL) FI\n'+original)
    (out/'fslocks.act').write_text(module)
    files=read_source(ROOT/'lib/fs/fsfiles.act').replace('USE EXEC','USE EXEC\nUSE DOSFAULTCONTROL',1)
    require(files.count('EXEC.AllocMem(')==2,'Stale file allocation probe')
    (out/'fsfiles.act').write_text(files.replace('EXEC.AllocMem(','DOSFAULTCONTROL.Allocate('))
    (out/'dosfaultcontrol.act').write_text("""MODULE DOSFAULTCONTROL
USE EXEC
PUBLIC BYTE failNext
PUBLIC BYTE POINTER FUNC Allocate(SIZE bytes LONGCARD flags)

  IF failNext<>0 THEN
    failNext==-1
    IF failNext=0 THEN
      RETURN(NULL)
    FI
  FI

RETURN(EXEC.AllocMem(bytes,flags))
ENDMODULE
""")
    paths=b''.join(path.ljust(32,b'\0') for path in (b'D1:',b'D1:TOOLS/SUB',b'D1:TOOLS/SUB/DATA.BIN'))
    return headless(t,out,mode,'dos_lock_allocation.act',paths,[(ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes()],
                    [dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],
                    override_sha256={name:sha256(out/name) for name in ('fslocks.act','fsfiles.act','dosfaultcontrol.act')})


def bounds(t,out,mode):
    import struct
    from mydos_fixtures import Image
    out.mkdir(parents=True,exist_ok=True)
    original=(ROOT/'tests/fixtures/mydos/mydos450-128.atr').read_bytes()
    disk=Image(original)
    def entry(start,name=b'ABCDEFGHXYZ',flags=16,count=8):
        return bytes([flags])+struct.pack('<HH',count,start)+name
    at=disk.offset(361);disk.data[at:at+16]=entry(500)
    for sector in range(500,636):
        at=disk.offset(sector);disk.data[at:at+128]=bytes(128)
    for index in range(16):
        at=disk.offset(500+index*8);disk.data[at:at+16]=entry(508+index*8)
        if index==15:disk.data[at+16:at+32]=entry(0,b'PAYLOAD_BIN',0x42,0)
    alias='ABCDEFGHIJKLMNOPQRSTUVWXYABCDEF'
    deep=alias+':'+('/'.join(['ABCDEFGH.XYZ']*16))
    cases=[('D1:CaSe.TxT',210),('D1:TOOLS//SUB',210),(deep,0),
           (deep+'/PAYLOAD_.BIN',0),(deep+'/ABCDEFGH.XYZ',217),('D1:'+('A'*252),210),('D1:'+('A'*253),210)]
    blob=bytearray();calls=[]
    for path,error in cases:
        calls.append(f'  Path(BYTE POINTER(${0xd1000+len(blob):x}),{error},{len(path)})')
        blob+=path.encode()+b'\0'
    (out/'dos-lock-bounds.inc').write_text('PROC Cases()\n'+'\n'.join(calls)+'\nRETURN\n')
    mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1),
            dict(alias=alias,unit=50,sectors=720,sector_bytes=128,profile=1)]
    return headless(t,out,mode,'dos_lock_bounds.act',bytes(blob),[original,bytes(disk.data)],mounts,
                    path_cases=[dict(path=p,error=e) for p,e in cases])


def headless(t,out,mode,source,paths,images,mounts,extra_data=(),**evidence):
    from test_sio_device import PIN as pin
    media=[]
    for index,raw in enumerate(images):
        path=out/f'volume{index}.atr';path.write_bytes(raw);media.append((path,sha256(path)))
    source_path=ROOT/'tests/programs'/source
    if source=='dos_lock_bounds.act':
        (out/source).write_bytes(source_path.read_bytes());source_path=out/source
    p=build(t,source_path,out,optimize=mode=='opt',tasks=True,task_capacity=8,
            console=False,dos_mounts=mounts,image_data=[(0xd1000,paths),(0xe0000,bytes(256)),*extra_data])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        b.config('diskemu','fastest')
        for index,(path,digest) in enumerate(media):b.mount(index,str(path.resolve()))
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Name failure checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        require(data(b,p['image'],'finished')==[1],'Incomplete lock-name failure probe')
        require(all(sha256(path)==digest for path,digest in media),'Media modified')
        checks=data(b,p['image'],'checks',True)
    return dict(status='pass',mode=mode,build=p['build'],runtime=runtime,machine=machine,
                observations=dict(checks=checks),media=[digest for path,digest in media],**evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',choices=('raw','opt'),required=True)
    p.add_argument('--only');p.add_argument('--output',type=Path,default=ROOT/'build/dos-lock-names')
    p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a=p.parse_args()
    t=compiler(a.compiler_dir)
    from test_dos_abi import run as abi
    from test_dos_directory import directory
    from test_dos_directories import run as directories
    from test_dos_files import run as files
    from test_dos_lifetime import run as lifetime
    from test_dos_streams import fixture
    cases=[('names-bank1',lambda out:names(t,out,a.case)),('names-bank3',lambda out:names(t,out,a.case,3)),
           ('allocation',lambda out:allocation(t,out,a.case)),('bounds',lambda out:bounds(t,out,a.case)),
           ('abi',lambda out:abi(t,out,a.case=='opt')),('current-directory',lambda out:directory(t,out,a.case)),
           ('directories',lambda out:directories(t,out,a.case,128)),
           ('corrupt-name',lambda out:directories(t,out,a.case,128,'name')),
           ('files',lambda out:files(t,out,a.case,128,capacity=8,concurrent=True)),
           ('lifetime',lambda out:lifetime(t,out,a.case)),
           ('large-read',lambda out:fixture(t,out,a.case,'dos_large_read.act',large=True))]
    for name,action in cases:
        if a.only and name not in a.only.split(','):continue
        out=a.output/a.case/name;out.mkdir(parents=True,exist_ok=True)
        print('Running lock names',a.case,name,flush=True)
        result=action(out);result['name']=name
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Lock-name qualification passed',a.case,flush=True)

if __name__=='__main__':main()
