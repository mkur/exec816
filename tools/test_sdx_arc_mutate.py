#!/usr/bin/env python3
"""Pinned ARC creation/mutation with independent archive decoding."""
import argparse,json,time,hashlib,struct
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from arc_archive import creation_corpus,read,member


def run(out):
    expected=creation_corpus()
    files={n:(ROOT/'build/sdx-inputs/arc'/n).read_bytes() for n in ['ARC.COM','ARCLST.OVL','ARCADD.OVL','ARCEXT.OVL']}
    unknown=bytearray(member('BINARY.BIN',b'old')+b'\x1a\0');unknown[19:23]=b'\0'*4
    files['UNKNOWN.ARC']=bytes(unknown)
    invalid={'FUTURE.ARC':((70<<9)|33,0), 'MONTH.ARC':((46<<9)|(13<<5)|1,0),
             'LEAP.ARC':((45<<9)|(2<<5)|29,0), 'TIME.ARC':((46<<9)|33,63<<5)}
    for name,(date,clock) in invalid.items():
        raw=bytearray(member('BINARY.BIN',b'old')+b'\x1a\0')
        struct.pack_into('<HH',raw,19,date,clock);files[name]=bytes(raw)
    files.update(expected);payload=bytearray();setup=[];addresses={}
    for name,raw in files.items():
        at=0x300000+len(payload);payload+=raw;addresses[name]=at
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
        if name in expected:setup.append(f'  Require(DOS.SetFileDate(BYTE POINTER(c"RAM:{name}"),@stamp)<>0)')
    dates=[]
    for i,name in enumerate(invalid,18):
        args='U '+name+' BINARY.BIN';temp=name.replace('.ARC','.XAR')
        dates.extend([f'  Run({i},BYTE POINTER(c"{args}"),{len(args)},20,156)',
                      f'  Verify(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${addresses[name]:x})),{len(files[name])},0)',
                      f'  Require(DOS.Open(BYTE POINTER(c"RAM:{temp}"),DOS.MODE_OLDFILE)=NULL AND DOS.IoErr()=DOS.ERROR_OBJECT_NOT_FOUND)'])
    source=out/'probe.act';source.write_text((ROOT/'tests/programs/sdx_arc_mutate.act').read_text().replace('SETUP_FILES','\n'.join(setup)).replace('DATE_CASES','\n'.join(dates)).replace('ADD_POINTER',f'BYTE POINTER(ADDRESS(${addresses["ARCADD.OVL"]:x}))').replace('UNKNOWN_POINTER',f'BYTE POINTER(ADDRESS(${addresses["UNKNOWN.ARC"]:x}))').replace('UNKNOWN_BYTES',str(len(unknown))))
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=32768
    (out/'memory.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,image_data=[(0x300000,bytes(payload))],memory_profile=out/'memory.json',dos_mounts=[dict(alias='RAM',format=3)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,program,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ['checks','currentCase','primary','secondary','reason','guestBank']},flush=True)
            abi=json.loads((ROOT/'abi/sdx.json').read_text())['runtime']
            context=b.memdump(abi['context_base'],abi['context_bytes']);bank=context[abi['fields']['bank']]*65536
            (out/'guest-context.bin').write_bytes(context);(out/'guest-bank.bin').write_bytes(b.memdump(bank,65536))
            print('event',int.from_bytes(context[abi['fields']['event']:abi['fields']['event']+2],'little'),'S',hex(int.from_bytes(context[abi['fields']['guest_s']:abi['fields']['guest_s']+2],'little')),flush=True);raise
        ownership(b,program,out)
        checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little');size=int.from_bytes(bytes(data(b,program['image'],'sessionBytes')),'little')
        counts=bytes(data(b,program['image'],'archiveBytes'));payload=bytes(data(b,program['image'],'archiveData'))
        archives=[payload[i*4096:i*4096+int.from_bytes(counts[i*4:i*4+4],'little')] for i in range(3)]
    entries=[]
    original=(ROOT/'build/sdx-arc/reference-create/readback/NEW.ARC').read_bytes()
    for i,raw in enumerate(archives):(out/f'archive-{i}.arc').write_bytes(raw)
    assert archives[0]==original,'Creation differs from pinned original SDX output'
    updated={**expected,'BINARY.BIN':b'updated','NEW.BIN':b'new','TEXT.BIN':b'fresh'}
    del updated['REPEAT.BIN']
    for i,(raw,wanted) in enumerate(zip(archives,[expected,updated,{'TEXT.BIN':b'fresh'}])):
        (out/f'archive-{i}.arc').write_bytes(raw)
        actual,metadata=read(raw);assert actual==wanted,(i,actual.keys(),wanted.keys())
        entries.append(metadata)
    assert entries[2][0]['method']==2
    return dict(status='pass',tier='development',checks=checks,session_bytes=size,entries=entries,runtime=runtime,machine=machine,build=program['build'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(out)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ARC mutation',result['status'],result['checks'],flush=True)
