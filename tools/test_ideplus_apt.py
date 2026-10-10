"""APT parsing/native sectors through native ATA PIO on independent host images."""
import argparse,json
from native_program import ROOT,build,compiler,execute,read_build,require
from test_ideplus import ide_emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from ideplus_media import pattern_fixture

def cases():
    for name,options in [('direct',{}),('even',{'even':True}),('mbr',{'mbr':True}),('chain',{'chained':True}),('even-chain',{'even':True,'chained':True})]:
        image,maps=pattern_fixture(**options);yield name,image,False
    image,_=pattern_fixture();image[0]=0x10;yield 'metadata-default',image,False
    for name in ('revision','cycle','overlap','leader-overlap','overflow','bad-offset','unsupported-128','unsupported-256'):
        image,_=pattern_fixture()
        if name=='revision': image[0]=0x20
        if name=='cycle':
            image[5]=2;image[8:12]=(1).to_bytes(4,'little')
            image[512:1024]=bytes(512);image[513:516]=b'APT';image[517]=2
            image[520:524]=(1).to_bytes(4,'little')
        if name=='overlap': image[50:58]=image[34:42]
        if name=='leader-overlap':
            image[32]|=0x40
            image[50:54]=(int.from_bytes(image[34:38],'little')+int.from_bytes(image[38:42],'little')).to_bytes(4,'little')
            image[48]|=0x40
        if name=='overflow': image[34:38]=(8190).to_bytes(4,'little')
        if name=='bad-offset': image[46:48]=(0xffff).to_bytes(2,'little')
        if name.startswith('unsupported-'):
            image[32]=(image[32]&~3)|(1 if name.endswith('128') else 2)
        yield name,image,not name.startswith('unsupported-')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--output',type=__import__('pathlib').Path,default=ROOT/'build/development/ideplus-ip2');v=a.parse_args()
    out=v.output;out.mkdir(parents=True,exist_ok=True)
    p=read_build(out) if v.reuse else build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/ideplus_apt.act',out,optimize=True,tasks=True,task_capacity=8,image_data=[(0x2dfff0,bytes([0xa5])*512)])
    for name,image,invalid in cases():
        dest=out/name;dest.mkdir(exist_ok=True);disk=dest/'ide.img';disk.write_bytes(image)
        with ide_emulator(dest,disk) as b:
            def before(b):
                for field,value in [('EXPECTEDFAILURE',invalid),('UNSUPPORTED',name.startswith('unsupported-'))]:
                    b.memload(next(d['address'] for d in p['image']['data'] if '_'+field+'_' in d['name']),bytes([value]))
            try:runtime,_=execute(b,p,before_run=before,timeout=90,frame_limit=4500)
            except Exception:
                print('case/checks',name,data(b,p['image'],'checks',True),flush=True)
                print('controller',b.memdump(p['build']['memory']['ideplus_storage']['BASE']+640,24).hex(),flush=True)
                raise
            clean_ownership(b,p,out);checks=data(b,p['image'],'checks',True)
        require(disk.read_bytes()==image,'Read modified APT fixture')
        (dest/'results.json').write_text(json.dumps(dict(status='pass',tier='development',build=p['build'],runtime=runtime,checks=checks),indent=2)+'\n')
        print('APT reads passed',name,flush=True)
