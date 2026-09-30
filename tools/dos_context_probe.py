"""Native caller-domain and exact register/result probe for DOSCORE.Current."""
from native_program import ROOT,build,command,execute,require,sha256
from test_banked import changed_image
from test_cooperative import data
from test_heap_api import clean_ownership
from generate_tasks import ABI

def run(b,t,out,optimize,variant):
    p=build(t,ROOT/'tests/programs/dos_context.act',out,optimize=optimize,tasks=True,dos_test=True)
    base=0xe0000;item=0x70000
    labels=dict(ITEM=item,CHECKS=next(d['address'] for d in p['image']['data'] if '_CHECKS_' in d['name']),CALL=p['labels']['dos_current'],VARIANT=variant)
    (out/'context.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',out,*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],'-o',out/'context.o',ROOT/'tests/programs/io_context.s'])
    command(['ld65','-C',out/'context.cfg','-o',out/'context.bin',out/'context.o'])
    p['image']['segments'] += [dict(address=base,bytes=list((out/'context.bin').read_bytes()),writable=False,executable=True),dict(address=item,bytes=[0]*26,writable=True,executable=False)]
    next(s for s in p['image']['segments'] if s['address']==p['image']['entry'])['bytes'][:4]=[0x5c,*base.to_bytes(3,'little')]
    changed_image(p)
    runtime,_=execute(b,p,expected_status=4 if variant else 0,timeout=240,frame_limit=12000)
    checks=data(b,p['image'],'checks',True)
    if variant:require(checks[7]==0,'Invalid DOS caller returned')
    else:
        slot=p['build']['memory']['dos_storage']['BASE']
        require(checks[:4]==[slot&65535,slot>>16,ABI['version'],0x2200] and checks[4]==checks[6] and checks[5]&255==0x12 and checks[5]&0x3c00==0 and checks[7]==1,'DOS native context/result: '+str(checks))
    clean_ownership(b,p,out)
    return dict(status='pass',case='context-'+str(variant),build=p['build'],runtime=runtime,checks=checks,probe_sha256=sha256(out/'context.bin'))
