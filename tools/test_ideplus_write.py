"""Verify durable logical writes and every persisted neighbour/padding byte."""
import sys,json
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from ideplus_media import pattern_fixture,put_sector
from test_cooperative import data
from test_heap_api import clean_ownership
if __name__=='__main__':
    out=ROOT/'build/development/ideplus-ip4/sectors';out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if '--reuse' in sys.argv else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_write.act',out,optimize=True,tasks=True,task_capacity=8,image_data=[(0x2dfff0,bytes([0xa5])*512)])
    for protected,failed in ((False,False),(True,False),(False,True)):
        dest=out/('failed-write' if failed else 'protected' if protected else 'writable');dest.mkdir(exist_ok=True)
        original,maps=pattern_fixture(readonly=protected);expected=bytearray(original);disk=dest/'ide.img';disk.write_bytes(original)
        if not protected and not failed:
            for mapping in maps:
                for sector,length,seed in [(0,mapping['size'],0x6c),(1,128,0xa7)]:
                    payload=bytes((i^seed^mapping['unit'])&255 for i in range(length))
                    put_sector(expected,mapping['start'],mapping['mode'],mapping['size'],sector,payload)
        with ide_emulator(dest,disk,writable=not failed) as b:
            def before(b):
                for field,value in [('PROTECTED',protected),('EXPECTEDERROR',3 if failed else 0)]:
                    b.memload(next(d['address'] for d in p['image']['data'] if '_IDEPLUSWRITETEST_'+field+'_' in d['name']),bytes([value]))
            try:runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            except Exception:
                print('checks',data(b,p['image'],'checks',True),flush=True)
                print('controller',b.memdump(p['build']['memory']['ideplus_storage']['BASE']+640,32).hex(),flush=True);raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==expected,'Unexpected physical media change, neighbour or padding corruption')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks),indent=2)+'\n')
        print('IDE logical writes passed',dest.name,flush=True)
