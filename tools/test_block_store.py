"""Focused real SIO verified writes through the common block request prefix."""
import json
from native_program import ROOT,build,compiler,execute,require,verify_machine,read_build,sha256
from os_boundary import emulator
from sector_images import disk_image
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
if __name__=='__main__':
    out=ROOT/'build/development/ideplus-ip0/block-store'
    out.mkdir(parents=True,exist_ok=True)
    import sys
    if '--reuse' in sys.argv:
        p=read_build(out)
        require(sha256(ROOT/'tests/programs/block_write.act')==p['build']['source_sha256'],'Changed source')
        for n,h in p['build']['task_inputs'].items():
            require(sha256(ROOT/n)==h,'Changed input: '+n)
    else:
        p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/block_write.act',out,
                optimize=True,tasks=True,image_data=[(0xafff0,bytes(256))])
    disk=out/'disk.atr';disk_image(disk,256,65535)
    original=disk.read_bytes()
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in {**PIN['configuration'],'diskemu':'generic56k','accuratedisk':False}.items():
            b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            b.mount(0,str(disk))
            for name,value in (('profile',4),('sectorBytes',256)):
                b.memload(next(d['address'] for d in p['image']['data'] if '_'+name.upper()+'_' in d['name']),value.to_bytes(2,'little'))
        try:
            runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
        except Exception:
            print("checks",data(b,p["image"],"checks",True),flush=True)
            raise
        clean_ownership(b,p,out)
        checks=data(b,p['image'],'checks',True)
    expected=bytearray(original)
    for sector,seed in ((1,0x6c),(4,0x69),(65534,0x93)):
        length=128 if sector<4 else 256
        offset=16+(sector-1)*128 if sector<4 else 400+(sector-4)*256
        expected[offset:offset+length]=bytes(i^seed for i in range(length))
    require(disk.read_bytes()==expected,'Persisted sector bytes or neighbours differ')
    (out/'results.json').write_text(json.dumps(dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=checks),indent=2)+'\n')
    print('Block verified writes and persisted neighbours passed',flush=True)
