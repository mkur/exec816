"""Public SDFS reads with real IDE staging, exact bytes and controlled failures."""
import argparse
import json
import shutil
from pathlib import Path
from native_program import ROOT, build, compiler, execute, read_build, require, sha256
from test_ideplus import ide_emulator
from ideplus_media import filesystem_fixture
from make_data_disk import make
from filesystem_audit import Audit, word
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage
from generate_memory import PROFILE
from library_paths import read_source


def run(out, reuse=False, selected=None):
    out.mkdir(parents=True, exist_ok=True)
    tree=out/'source';tree.mkdir(exist_ok=True)
    payload=bytes((i^(i>>8)^(i>>16))&255 for i in range(512*255+7))
    (tree/'LARGE.BIN').write_bytes(payload)
    make(out/'source.atr',tree,binary_names=['LARGE.BIN'],sector_bytes=512,sectors=1440)
    initial=(out/'source.atr').read_bytes()
    # Keep the production transfer/collection path, injecting at exact worker
    # boundaries without adding a production callback or reservation.
    shutil.copyfile(ROOT/'tests/programs/readrangeprobe.act',out/'readrangeprobe.act')
    source=read_source(ROOT/'lib/fs/fsio.act')
    source=source.replace('USE FSSTATUS\n','USE FSSTATUS\nUSE READRANGEPROBE\n',1)
    marker='  service.work.ioError=BLOCKIO.FinishFetchRange('
    require(source.count(marker)==1,'Changed completion checkpoint')
    source=source.replace(marker,'  READRANGEPROBE.BeforeComplete(service)\n'+marker)
    marker='RETURN(FSSTATUS.DONE)'
    require(source.count(marker)==1,'Changed successful completion checkpoint')
    source=source.replace(marker,'  READRANGEPROBE.AfterComplete(service)\n\n'+marker)
    (out/'fsio.act').write_text(source)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=4352
    (out/'profile.json').write_text(json.dumps(profile))
    mounts=[dict(alias='IDE',device='ideplus.device',unit=2,profile=0,format=2,sectors=1440,sector_bytes=512)]
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/ideplus_file_reads.act',out,optimize=True,tasks=True,
        task_capacity=8,console=True,system_mount='IDE',dos_mounts=mounts,
        memory_profile=out/'profile.json',image_data=[(0x2cffef,bytes([0xa5])*4098),(0x300000,bytes(len(payload)))])
    for name in ('normal','fragmented','sparse','no-cache','failed','break-first','break-middle'):
        if selected and name not in selected:continue
        dest=out/name;dest.mkdir(exist_ok=True)
        audit=Audit(initial);audit.sdfs();image=audit.image
        root=word(image.sector(1),9);root_data=word(image.sector(root),4)
        start=word(image.sector(root_data),24)
        if name=='fragmented':
            at=image.offset(start)
            first=word(image.data,at+8);second=word(image.data,at+12)
            first_bytes=image.sector(first);second_bytes=image.sector(second)
            image.data[at+8:at+10]=second.to_bytes(2,'little')
            image.data[at+12:at+14]=first.to_bytes(2,'little')
            image.data[image.offset(first):image.offset(first)+512]=second_bytes
            image.data[image.offset(second):image.offset(second)+512]=first_bytes
        elif name=='sparse':
            at=image.offset(start)+8;sector=word(image.data,at)
            image.data[at:at+2]=b'\0\0'
            bitmap=word(image.sector(1),16)
            image.data[image.offset(bitmap)+sector//8]|=0x80>>(sector&7)
            header=image.offset(1)
            free=word(image.data,header+13)
            image.data[header+13:header+15]=(free+1).to_bytes(2,'little')
        checked=Audit(bytes(image.data));allocation=checked.sdfs()
        expected=checked.files['LARGE.BIN']
        media,_=filesystem_fixture(bytes(image.data));disk=dest/'ide.img';disk.write_bytes(media)
        scenario={'failed':2,'break-first':1,'break-middle':3}.get(name,0)
        with ide_emulator(dest,disk) as b:
            def before(b):
                for field,value in [('FILEBYTES',len(expected).to_bytes(4,'little')),
                                    ('NOCACHE',bytes([name=='no-cache'])),('SCENARIO',bytes([scenario]))]:
                    at=next(d['address'] for d in p['image']['data'] if '_IDEPLUSFILEREADS_'+field+'_' in d['name'])
                    b.memload(at,value)
                b.memload(0x300000,expected)
            try:runtime,_=execute(b,p,before_run=before,timeout=180,frame_limit=9000)
            except Exception:
                print(name,'checks',data(b,p['image'],'checks',True),
                      'error',data(b,p['image'],'readError',True),flush=True);raise
            clean_ownership(b,p,out)
            observations={key:data(b,p['image'],key,True) for key in ('checks','workspaceBytes')}
            probe={key:data(b,p['image'],key) for key in ('groups','fired')}
            stacks=stack_usage(b,p['build']['memory'])
        require(disk.read_bytes()==media,'Read changed native filesystem media')
        result=dict(status='pass',tier='development',case=name,build=p['build'],runtime=runtime,
                    observations=observations,probe=probe,allocation=allocation,
                    content_sha256=sha256(tree/'LARGE.BIN'),stacks=stacks)
        (dest/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('IDE file reads passed',name,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true');parser.add_argument('--case',action='append')
    args=parser.parse_args();run(args.output,args.reuse,args.case)
