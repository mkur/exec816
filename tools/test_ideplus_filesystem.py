"""Read native SDFS-512 alongside floppy MyDOS/SDFS and RAM through DOS."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from filesystem_audit import Audit
from generate_dos_mounts import encode
from ideplus_media import filesystem_fixture,sdfs_image
from make_data_disk import make
from test_cooperative import data
from test_heap_api import clean_ownership
from generate_memory import PROFILE


def mounts(ide_audit,sio_audit,fs,writable=False):
    return [dict(alias='D1',unit=49,sectors=sio_audit.image.count,sector_bytes=256,format=1 if fs=='mydos' else 2,profile=4),
            dict(alias='IDE',unit=2,access='readwrite' if writable else 'readonly',device='ideplus.device',sectors=ide_audit.image.count,sector_bytes=512,format=2,profile=0),
            dict(alias='RAM',format=3)]


def run(out,reuse=False,failed_write=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr'
    atr=sdfs_image(source,out/'stage.atr')
    audit=Audit(atr);audit.sdfs()
    sio_initial=Audit((ROOT/'tests/fixtures/filesystem-write/mydos-256.atr').read_bytes());sio_initial.mydos()
    profile=out/'profile.json';value=json.loads(PROFILE.read_text());value['image_data_bytes']=4096;profile.write_text(json.dumps(value))
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_filesystem.act',out,optimize=True,tasks=True,task_capacity=8,console_deferred=True,memory_profile=profile,dos_mounts=mounts(audit,sio_initial,'mydos'),image_data=[(0x2d1000,bytes(8192)),(0x2e0000,bytes(0x30000))])
    scenarios=[('mydos','mydos',False,False),('sdfs','sdfs',False,False),('map-boundary','sdfs',False,False),('bad-geometry','mydos',False,True)]
    if failed_write:scenarios.append(('failed-write','mydos',True,False))
    for name,fs,failwrite,admission in scenarios:
        dest=out/name;dest.mkdir(exist_ok=True)
        ide_atr=atr
        if name=='map-boundary':
            tree=dest/'tree';tree.mkdir(exist_ok=True)
            payload=bytes((i^(i>>8)^(i>>16))&255 for i in range(512*255+7))
            (tree/'LARGE.BIN').write_bytes(payload)
            make(dest/'large.atr',tree,binary_names=['LARGE.BIN'],sector_bytes=512,sectors=2000)
            ide_atr=(dest/'large.atr').read_bytes()
        ide_audit=Audit(ide_atr);ide_audit.sdfs()
        raw,mapping=filesystem_fixture(ide_atr,readonly=not failwrite);disk=dest/'ide.img';disk.write_bytes(raw)
        sio_atr=(ROOT/f'tests/fixtures/filesystem-write/{fs}-256.atr').read_bytes()
        sio_audit=Audit(sio_atr);getattr(sio_audit,fs)()
        sio=dest/'sio.atr';sio.write_bytes(sio_atr)
        paths=bytearray();expected=bytearray();count=0
        for alias,files in [('IDE',ide_audit.files),('D1',sio_audit.files)]:
            for filename,payload in sorted(files.items()):
                row=bytearray(72);path=(alias+':'+filename).encode()+b'\0';require(len(path)<=64,'Long path')
                row[:len(path)]=path;row[64:72]=len(payload).to_bytes(4,'little')+len(expected).to_bytes(4,'little')
                paths+=row;expected+=payload;count+=1
        require(len(paths)<=8192 and len(expected)<=0x30000,'Fixture provider capacity')
        with ide_emulator(dest,disk) as b:
            b.config('diskemu','generic56k')
            def before(b):
                b.mount(0,str(sio))
                configured=mounts(ide_audit,sio_audit,fs,failwrite)
                if admission:configured[1]['sectors']-=1
                b.memload(p['build']['task_storage']['BASE']+0x900,encode(configured))
                for field,value in [('FAILWRITE',failwrite),('FAILADMISSION',admission)]:
                    b.memload(next(d['address'] for d in p['image']['data'] if '_IDEPLUSFILESYSTEM_'+field+'_' in d['name']),bytes([value]))
                b.memload(0x2d1000,paths);b.memload(0x2e0000,expected)
                b.memload(next(d['address'] for d in p['image']['data'] if '_IDEPLUSFILESYSTEM_COUNT_' in d['name']),count.to_bytes(2,'little'))
            try:runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=15000)
            except Exception:
                print('FS/checks/error',fs,data(b,p['image'],'checks',True),data(b,p['image'],'lastError',True),flush=True);raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==raw and sio.read_bytes()==sio_atr,'Read-only filesystem changed media')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks,files=count,bytes=len(expected)),indent=2)+'\n')
        print('IDE filesystem coexistence passed',name,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=ROOT/'build/development/ideplus-ip3');a.add_argument('--reuse',action='store_true');a.add_argument('--failed-write',action='store_true');v=a.parse_args();run(v.output,v.reuse,v.failed_write)
