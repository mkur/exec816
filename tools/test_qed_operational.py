#!/usr/bin/env python3
"""Actual QED writer: physical full media, foreground BREAK and pinned SIO faults."""
import argparse,copy,hashlib,json,os,struct,shutil
from pathlib import Path
from native_program import ROOT,require,sha256
from qed_probe import run_probe
from test_qed_saving import heap
from os_boundary import run_to
from test_cooperative import data


def observe(mode,filesystem,selector=None,fault=None,point=1):
    def interaction(b,p,app,record,owner):
        delta=owner['image_base']-(app['abi']['link_bank']<<16)
        sy={n:v+delta for n,v in app['image']['symbols'].items()}
        def put(name,value):b.memload(sy[name],struct.pack('<H',value))
        def reach(condition):
            b.bp_clear_all();b.bp_set(p['labels']['native_cop'],condition=condition)
            run_to(b,p['labels']['native_cop'],condition=condition,timeout=480,frame_limit=30000)
        put('QedOperationalMode',mode)
        if 'QedFilesystemMode' in sy:put('QedFilesystemMode',0)
        if mode:
            put('QedOperationalPoint',point)
            reach('(dw($%x)=1)&(dw($%x)=%d)'%(sy['QedOperationalPoint'],sy['QedOperationalWrites'],point if mode==2 else 1))
            if mode==1:
                put('QedOperationalGate',1)
                state=p['build']['task_storage']['BASE']+0x800
                condition='(db($%x)=7)&(db($%x)=2)&(dw($%x)=0)'%(state+1,state+4,state+20)
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                run_to(b,p['labels']['native_irq'],condition=condition,timeout=240,frame_limit=12000)
                record['wire_activation']=dict(state=b.memdump(state,128).hex(),clock=b.eval_expr('@clk'),
                    point='Actual WRITE payload transmitted, before checksum/data ACK/terminal completion')
                selector.write_text(fault+'\n')
            else:
                def at(name):return next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_CPROCESSTEST_'+name.upper()+'_'))
                b.memload(at('control'),struct.pack('<H',1));reach('dw($%x)=2'%at('phase'))
            put('QedOperationalGate',1)
        heap(b,p,app,record,owner,timeout=1500 if not mode else 480,
             frame_limit=100000 if not mode else 30000)
        result=list(struct.unpack('<12I',b.memdump(sy['QedOperationalResult'],48))) if 'QedOperationalResult' in sy else None
        memory=list(struct.unpack('<8I',b.memdump(sy['QedOperationalMemory'],32)))
        item=dict(mode=mode,result=result,memory=memory,cases=b.peek16(sy['QedOperationalCases']))
        if mode==1:
            hardware=b.memdump(p['build']['task_storage']['BASE']+0x800,128)
            require(hardware[45]==int(fault=='protocol'),'Wrong physical offline latch')
            require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained physical caller buffer')
            item.update(hardware=hardware.hex(),fault=fault,reset_required=fault=='protocol')
        if mode==2:require(result[3]==(4096 if point==2 else 0),'Wrong committed prefix at BREAK')
        record.setdefault('operational',[]).append(item)
        def retired():
            totals=list(struct.unpack('<4I',b.memdump(sy['totals'],16)))
            require(totals[:3]==[0,0,0],'Retired writer retained private allocations')
            item['private_after_retirement']=totals
        return retired
    return interaction


def initial(path,filesystem,directory=False):
    # A reused supervisor must not import the reader cohort's large fixtures.
    # Build the selected disposable volume from exactly this probe's inputs.
    from make_data_disk import make
    media=path.parent/'operational-media';media.mkdir(exist_ok=True)
    for name in ('PROBE.APP','DESKTOP.RSC','HELLO','DEST.TXT','DEST.BAK','KEEP.BIN'):
        shutil.copyfile(path.parent/'media'/name,media/name)
    if directory:
        require(filesystem=='mydos','Fixed root exhaustion requires MyDOS')
        for i in range(58):(media/('Z%07d.TXT'%i)).write_bytes(b'')
    make(path,media,binary_names={p.name for p in media.iterdir()},
         filesystem=filesystem,sector_bytes=256,sectors=720)
    path.with_name('initial.atr').write_bytes(path.read_bytes())


def audit(out,filesystem,mode,directory=False):
    from filesystem_audit import Audit
    from mydos_fixtures import Image
    from test_filesystem_write_edges import entry
    before=Audit((out/'initial.atr').read_bytes());getattr(before,filesystem)()
    after=Image((out/'system.atr').read_bytes());files=('DEST.TXT','DEST.BAK','KEEP.BIN')
    for sector,owner in before.owners.items():
        if owner.split(' ')[0] in files:
            require(before.image.sector(sector)==after.sector(sector),'Unrelated payload/map changed: '+owner)
    for name in files:
        positions,_,_=entry(Image(before.image.data),filesystem,name)
        require(bytes(before.image.data[i] for i in positions)==bytes(after.data[i] for i in positions),
                'Unrelated directory entry changed: '+name)
    data=dict(status='pass',media_sha256=sha256(out/'system.atr'),initial_sha256=sha256(out/'initial.atr'),
        preserved=list(files),scope='Original D/B/KEEP bytes and metadata; unsafe fault images are not declared healthy')
    oracle=Audit(after.data)
    try:allocation=getattr(oracle,filesystem)()
    except ValueError as error:
        require(mode==1,'Logical case left an inconsistent image: '+str(error));data['allocation_error']=str(error)
    else:
        data['allocation']=allocation
        if not mode and not directory:
            expected=b''.join(b'\t'+bytes([97+i])*1021+bytes([255 if i%2 else 128])+b'\n' for i in range(4))
            require(oracle.files.get('AUDIT.TXT')==oracle.files.get('AUDIT.BAK')==expected,'Operational D/B bytes differ')
            require(not any(n.startswith('Q') and n.endswith(('.TMP','.OLD')) for n in oracle.files),'Unexpected logical recovery artifact')
        data['artifacts']={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
            for n,v in oracle.files.items() if n.startswith(('AUDIT','Q')) and n.endswith(('.TXT','.BAK','.TMP','.OLD'))}
    (out/'operational-audit.json').write_text(json.dumps(data,indent=2)+'\n');return data


def run(out,native_from,filesystem,group,fault='device',point=1):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    execution=dict(sectors=720);selector=None;mode={'normal':0,'directory':0,'transport':1,'break':2}[group]
    support=[]
    if group=='directory':
        generated=out/'app/qed-operational-support.inc';generated.parent.mkdir(parents=True,exist_ok=True)
        fixture=ROOT/'tests/programs/qed_operational.c'
        prefix=fixture.read_text().split('static int normal_cases(void)')[0]
        generated.write_text(prefix.replace('#include \"qed_stage.c\"','#include \"'+str(ROOT/'tests/programs/qed_stage.c')+'\"'))
        support=[fixture,generated]
    if mode:
        fault_pin=json.loads((ROOT/'toolchain/qed-saving-sio-faults.json').read_text())
        pin=copy.deepcopy(fault_pin);pin['configuration']['diskemu']='generic56k'
        binary=(ROOT/pin['fault_responder']['binary']).parent
        require(sha256(binary/'AltirraBridgeServer')==fault_pin['fault_responder']['binary_sha256'],'Unpinned SIO responder')
        selector=out/'fault.txt';selector.write_text('none\n');os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
        execution=dict(binary=binary,pin=pin,drive=7,unit=56,sectors=720,alias='D8',system_mount='D8',
                       status=0xff93 if mode==1 and fault=='protocol' else 0)
    r=run_probe(out,'qed_directory_full.c' if group=='directory' else 'qed_operational.c',native_units=('path.c','stage.c','save.c'),qed_units=('memory.c','clipbrd.c'),
        native_from=native_from,filesystem=filesystem,writable=True,ram=True,minimum_stack=2048,
        lifetimes=1 if mode else 2,interactive_lifetimes=not mode,
        fixture_source=ROOT/'tests/programs/qed_operational.act' if mode else None,
        execution=execution,interaction=observe(mode,filesystem,selector,fault,point),prepare_media=lambda p,f:initial(p,f,group=='directory'),
        media_files={'DEST.TXT':b'old','DEST.BAK':b'older','KEEP.BIN':bytes(range(256))},
        extra_inputs=[ROOT/'tests/programs/qed_stage.c',*support],
        calls={'stage.c':dict(Fwrite='QedOperationalWrite',DeleteFile='QedOperationalDelete'),
               'files.c':dict(Close='QedOperationalClose'),
               'save.c':dict(Rename='QedOperationalRename',DeleteFile='QedOperationalDelete')})
    if mode:require(r['last_secondary'][0]==r['operational'][0]['result'][1],
                    'Process finalization lost the original save cause')
    audit(out,filesystem,mode,group=='directory');return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path);p.add_argument('--filesystem',choices=('mydos','sdfs'),default='sdfs')
    p.add_argument('--group',choices=('normal','directory','transport','break'),default='normal')
    p.add_argument('--fault',choices=('device','protocol'),default='device');p.add_argument('--point',type=int,choices=(1,2),default=1)
    a=p.parse_args();r=run(a.output,a.native_from,a.filesystem,a.group,a.fault,a.point);print(r['status'],r['completed'])
