"""APT parsing/packing through native ATA PIO on independent host images."""
import json,sys
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from ideplus_media import pattern_fixture

def cases():
    for name,options in [('direct',{}),('even',{'even':True}),('mbr',{'mbr':True}),('chain',{'chained':True}),('even-chain',{'even':True,'chained':True})]:
        image,maps=pattern_fixture(**options);yield name,image,False
    for name in ('revision','cycle','overlap','overflow','bad-offset'):
        image,_=pattern_fixture()
        if name=='revision': image[0]=0x20
        if name=='cycle':
            image[5]=2;image[8:12]=(1).to_bytes(4,'little')
            image[512:1024]=bytes(512);image[513:516]=b'APT';image[517]=2
            image[520:524]=(1).to_bytes(4,'little')
        if name=='overlap': image[50:58]=image[34:42]
        if name=='overflow': image[34:38]=(8190).to_bytes(4,'little')
        if name=='bad-offset': image[46:48]=(0xffff).to_bytes(2,'little')
        yield name,image,True

if __name__=='__main__':
    out=ROOT/'build/development/ideplus-ip2';out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if '--reuse' in sys.argv else build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/ideplus_apt.act',out,optimize=True,tasks=True,task_capacity=8,image_data=[(0x2dfff0,bytes([0xa5])*512)])
    for name,image,invalid in cases():
        dest=out/name;dest.mkdir(exist_ok=True);disk=dest/'ide.img';disk.write_bytes(image)
        with ide_emulator(dest,disk) as b:
            def before(b):b.memload(next(d['address'] for d in p['image']['data'] if '_EXPECTEDFAILURE_' in d['name']),bytes([invalid]))
            try:runtime,_=execute(b,p,before_run=before,timeout=90,frame_limit=4500)
            except Exception:
                print('case/checks',name,data(b,p['image'],'checks',True),flush=True)
                print('controller',b.memdump(p['build']['memory']['ideplus_storage']['BASE']+640,24).hex(),flush=True)
                raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==image,'Read modified APT fixture')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks),indent=2)+'\n')
        print('APT reads passed',name,flush=True)
