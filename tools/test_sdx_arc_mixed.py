#!/usr/bin/env python3
"""A4: sequential resident MD5/ARC with busy rejection, native peer and SDFS, BREAK, ownership and shell."""
import argparse,hashlib,json,time
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,read_build
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from sdfs_reference import make,extract
from arc_archive import member,read
from filesystem_audit import Audit


def fixture(out):
    original=member('OLD.BIN',b'old')+b'\x1a\0'
    payload=bytearray();setup=[]
    files={n:(ROOT/'build/sdx-inputs/arc'/n).read_bytes() for n in ['ARC.COM','ARCLST.OVL','ARCADD.OVL','ARCEXT.OVL']}
    files['MD5']=(ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes()
    for name,raw in files.items():
        at=0x300000+len(payload);payload+=raw
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
    at=0x300000+len(payload);payload+=original
    source=(ROOT/'tests/programs/sdx_arc_mixed.act').read_text().replace('SHELL_INCLUDE',str(ROOT/'examples/shell/shell-session.inc')).replace('SETUP_FILES','\n'.join(setup)).replace('ORIGINAL_BYTES',str(len(original))).replace('ORIGINAL_POINTER',f'BYTE POINTER(ADDRESS(${at:x}))')
    (out/'probe.act').write_text(source)
    return out/'probe.act',[(0x300000,bytes(payload))],original


def run(out,reuse=False):
    source,payload,original=fixture(out)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=16384
    (out/'memory.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=12,console=True,console_test=True,sdx=True,sdx_drive_a='D1:',image_data=payload,memory_profile=out/'memory.json',dos_mounts=[dict(alias='RAM',format=3),dict(alias='D1',device='sio.device',unit=49,sectors=1024,sector_bytes=256,format=2,access='readwrite',profile=4)])
    directory=out/'source';directory.mkdir(exist_ok=True)
    a=bytes((i*37+i//251)&255 for i in range(4096));bb=bytes((i*53+i//113)&255 for i in range(8192))
    for name,raw in {'A.BIN':a,'B.BIN':bb,'FAIL.ARC':original,'SHARE.ARC':original}.items():(directory/name).write_bytes(raw)
    make(out/'volume.atr',directory,1024,256,'ARCMIX')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','generic56k');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.mount(0,str(out/'volume.atr'))
        try:runtime,_=execute(b,program,timeout=480,frame_limit=24000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ['checks','currentCase','primary','secondary','reason','breakTicks','elapsed','peerProgress']},flush=True);raise
        ownership(b,program,out)
        observed={k:int.from_bytes(bytes(data(b,program['image'],k)),'little') for k in ['checks','breakTicks','sessionBytes']}
        for name,stride in [('elapsed',2),('guestGuardBytes',2),('peerProgress',4)]:
            values=bytes(data(b,program['image'],name));observed[name]=[int.from_bytes(values[i:i+stride],'little') for i in range(0,len(values),stride)]
        for name,count in [('hashOutput','hashBytes'),('shellOutput','shellBytes')]:
            n=int.from_bytes(bytes(data(b,program['image'],count)),'little');observed[name]=bytes(data(b,program['image'],name))[:n].hex()
        time.sleep(3);b._cmd_ok('EJECT drive=0')
    assert bytes.fromhex(observed['hashOutput'])==b'MD5 (A.BIN) = '+hashlib.md5(a).hexdigest().upper().encode()+b'\x9b'
    assert b'OLD.BIN' in bytes.fromhex(observed['shellOutput']) and b'A.BIN' in bytes.fromhex(observed['shellOutput'])
    Audit((out/'volume.atr').read_bytes()).sdfs();extract(out/'volume.atr',out/'readback')
    expected={'HASH.ARC':{'A.BIN':a},'ONE.ARC':{'A.BIN':a},'TWO.ARC':{'B.BIN':bb},'KEEP.ARC':{'B.BIN':bb},'FAIL.ARC':{'OLD.BIN':b'old','A.BIN':a},'SHARE.ARC':{'OLD.BIN':b'old','A.BIN':a}}
    entries={}
    for name,wanted in expected.items():
        actual,entries[name]=read((out/'readback'/name).read_bytes());assert actual==wanted,name
    assert (out/'readback'/'A.BIN').read_bytes()==a and (out/'readback'/'B.BIN').read_bytes()==bb
    assert not list((out/'readback').glob('*.XAR')) and not list((out/'readback').glob('*.BAK'))
    return dict(status='pass',tier='development',observed=observed,entries=entries,runtime=runtime,machine=machine,build=program['build'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(out,a.reuse)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ARC mixed',result['status'],result['observed'],flush=True)
