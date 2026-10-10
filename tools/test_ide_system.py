"""Fixed IDE SYS selection and boot-record fallback, through emitted code."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,read_build,require
from generate_memory import PROFILE
from test_ideplus import ide_emulator
from ideplus_media import filesystem_fixture
from test_cooperative import data
from test_heap_api import clean_ownership

def run(output,reuse=False,ide_only=False):
    output.mkdir(parents=True,exist_ok=True)
    atr=(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr').read_bytes()
    raw,mapping=filesystem_fixture(atr)
    media=output/'ide.img';media.write_bytes(raw)
    profile=output/'profile.json';value=json.loads(PROFILE.read_text());value['image_data_bytes']=4096;profile.write_text(json.dumps(value))
    mounts=[dict(alias='SYSTEM',device='ideplus.device',unit=2,profile=0,sectors=mapping['sectors'],sector_bytes=256,format=2)]
    p=read_build(output) if reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ide_system.act',output,optimize=True,tasks=True,task_capacity=8,console_deferred=True,memory_profile=profile,dos_mounts=mounts,system_mount='SYSTEM',sio_enabled=not ide_only)
    if ide_only:
        require(not any(r['name'].startswith(('M_SIODRIVER_','M_SIOADAPTER_')) for r in p['image']['routines']),'SIO implementation linked')
        require('sio_start' not in p['labels'],'Native SIO engine linked')
    observations=[]
    with ide_emulator(output,media) as b:
        for label,drive,status in [('default',0,0),('reject-sio',2,1)]:
            def before(b):
                b.poke(p['build']['memory']['boot_config']['address']+6,drive)
                at=next(d['address'] for d in p['image']['data'] if '_IDESYSTEM_EXPECTEDSTATUS_' in d['name'])
                b.memload(at,bytes([status]))
                at=next(d['address'] for d in p['image']['data'] if '_IDESYSTEM_NOSIO_' in d['name'])
                b.memload(at,bytes([ide_only]))
            runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            clean_ownership(b,p,output)
            observations.append(dict(case=label,checks=data(b,p['image'],'checks',True),runtime=runtime))
    require(media.read_bytes()==raw,'Read-only system media changed')
    (output/'results.json').write_text(json.dumps(dict(status='pass',tier='development',cases=observations,build=p['build']),indent=2)+'\n')
    print('IDE SYS selection passed',flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id0');a.add_argument('--reuse',action='store_true');a.add_argument('--ide-only',action='store_true');v=a.parse_args();run(v.output,v.reuse,v.ide_only)
