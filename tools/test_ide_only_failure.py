"""IDE-only admission, remount, shared offline/cache rejection and RAM survival."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,build,execute,require,read_build
from make_data_disk import make
from build_ide_media import write
from test_ideplus import ide_emulator
from test_heap_api import clean_ownership
from test_cooperative import data
from os_boundary import run_to

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id6-failure');v=a.parse_args();out=v.output;out.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=4096
    (out/'profile.json').write_text(json.dumps(profile))
    mounts=[dict(alias='SYSTEM',device='ideplus.device',unit=1,profile=0,format=2,sectors=1440,sector_bytes=512),
            dict(alias='WORK',device='ideplus.device',unit=2,profile=0,format=2,sectors=1440,sector_bytes=512,access='readwrite'),dict(alias='RAM',format=3)]
    p=read_build(out) if v.reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ide_only_failure.act',out,optimize=True,tasks=True,task_capacity=8,console=True,heap_probe=True,dos_mounts=mounts,system_mount='SYSTEM',sio_enabled=False,memory_profile=out/'profile.json')
    (out/'source').mkdir(exist_ok=True);(out/'source/README.TXT').write_text('IDE-only partition\n')
    make(out/'stage.atr',out/'source',sector_bytes=512,sectors=1440)
    record=write(out/'original.img',out/'stage.atr',out/'stage.atr');raw=(out/'original.img').read_bytes()
    for scenario,name in enumerate(('remount','absent','protected','write-error','verify-error')):
        dest=out/name;dest.mkdir(exist_ok=True);image=bytearray(raw)
        if scenario==2:image[32+12]|=0x80;image[17*16+12]|=0x80
        disk=dest/'ideplus.img';disk.write_bytes(image)
        with ide_emulator(dest,disk,absent=scenario==1,writable=scenario!=3) as b:
            def before(b):
                at=next(d['address'] for d in p['image']['data'] if '_IDEONLYFAILURE_SCENARIO_' in d['name'])
                b.memload(at,bytes([scenario]))
                if scenario==4:
                    base=p['build']['memory']['ideplus_storage']['BASE']
                    b.memload(p['labels']['ideplus_probe_8'],b'\x22'+p['labels']['ideplus_probe_verify'].to_bytes(3,'little'))
                    cond=f'db(${base+768+6:x})=1'
                    b.bp_set(p['labels']['native_cop'],condition=cond)
                    run_to(b,p['labels']['native_cop'],12000,180,cond)
                    buffer=int.from_bytes(b.memdump(base+640,3),'little')
                    original=b.peek(buffer)
                    b.memload(buffer,bytes([original[0]^1]))
                    b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        after=disk.read_bytes();m=record['partitions'][1];lo=m['start']*512;hi=lo+m['physical']*512
        require(after[:lo]==image[:lo] and after[hi:]==image[hi:],'Failure mutated SYS or metadata')
        if scenario in (1,2,3):require(after==image,'Rejected write changed media')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',case=name,checks=checks,runtime=runtime,build=p['build']),indent=2)+'\n')
        print('IDE-only case passed',name,flush=True)
