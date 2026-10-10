"""Read APT-backed MyDOS/SDFS alongside SIO and RAM through ordinary DOS."""
import json,sys
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from filesystem_audit import Audit
from generate_dos_mounts import encode
from ideplus_media import filesystem_fixture
from test_cooperative import data
from test_heap_api import clean_ownership
from generate_memory import PROFILE

def mounts(audit,fs):
    return [dict(alias='D1',unit=49,sectors=audit.image.count,sector_bytes=256,format=1 if fs=='mydos' else 2,profile=4),
            dict(alias='IDE',unit=2,device='ideplus.device',sectors=audit.image.count,sector_bytes=256,format=1 if fs=='mydos' else 2,profile=0),
            dict(alias='RAM',format=3)]

if __name__=='__main__':
    out=ROOT/'build/development/ideplus-ip3';out.mkdir(parents=True,exist_ok=True)
    initial=Audit((ROOT/'tests/fixtures/filesystem-write/mydos-256.atr').read_bytes());initial.mydos()
    profile=out/'profile.json';value=json.loads(PROFILE.read_text());value['image_data_bytes']=4096;profile.write_text(json.dumps(value))
    p=read_build(out) if '--reuse' in sys.argv else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_filesystem.act',out,optimize=True,tasks=True,task_capacity=8,console_deferred=True,memory_profile=profile,dos_mounts=mounts(initial,'mydos'),image_data=[(0x2d1000,bytes(8192)),(0x2e0000,bytes(32768))])
    for fs in ('mydos','sdfs'):
        dest=out/fs;dest.mkdir(exist_ok=True);atr=(ROOT/f'tests/fixtures/filesystem-write/{fs}-256.atr').read_bytes();audit=Audit(atr);getattr(audit,fs)()
        raw,mapping=filesystem_fixture(atr);disk=dest/'ide.img';disk.write_bytes(raw)
        sio=dest/'sio.atr';sio.write_bytes(atr)
        paths=bytearray();expected=bytearray();count=0
        for alias in ('IDE','D1'):
            for name,payload in sorted(audit.files.items()):
                row=bytearray(72);name=(alias+':'+name).encode()+b'\0';require(len(name)<=64,'Long path')
                row[:len(name)]=name;row[64:68]=len(payload).to_bytes(2,'little')+len(expected).to_bytes(2,'little')
                paths+=row;expected+=payload;count+=1
        with ide_emulator(dest,disk) as b:
            b.config('diskemu','generic56k')
            def before(b):
                b.mount(0,str(sio));b.memload(p['build']['task_storage']['BASE']+0x900,encode(mounts(audit,fs)))
                b.memload(0x2d1000,paths);b.memload(0x2e0000,expected)
                b.memload(next(d['address'] for d in p['image']['data'] if '_IDEPLUSFILESYSTEM_COUNT_' in d['name']),count.to_bytes(2,'little'))
            try:runtime,_=execute(b,p,before_run=before,timeout=180,frame_limit=9000)
            except Exception:
                print('FS/checks/error',fs,data(b,p['image'],'checks',True),data(b,p['image'],'lastError',True),flush=True);raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==raw and sio.read_bytes()==atr,'Read-only filesystem changed media')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks,files=count),indent=2)+'\n')
        print('IDE filesystem coexistence passed',fs,flush=True)
