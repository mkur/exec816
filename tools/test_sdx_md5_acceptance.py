#!/usr/bin/env python3
"""M2 real MD5 command/list/error/concurrency checks through public DOS."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from native_program import ROOT, build, compiler, read_build, verify_machine
from os_boundary import emulator
from sdx_md5_audit import audit
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN


def corpus():
    good=b'900150983cd24fb0d6963f7d28e17f72  ABC.BIN\n'
    files={'ABC.BIN':b'abc','EMPTY.BIN':b'',
           'BIG.BIN':bytes((i*37+i//251)&255 for i in range(65537)),
           'GOOD.MD5':good,'BAD.MD5':good.replace(b'90015098',b'00015098'),
           'ATARI.MD5':good.replace(b'\n',b'\x9b'),
           'CRLF.MD5':good.replace(b'\n',b'\r\n'),
           'FINAL.MD5':good.rstrip(b'\n'),
           'BSD.MD5':b'MD5 (ABC.BIN) = 900150983cd24fb0d6963f7d28e17f72\x9b',
           'EMPTY.MD5':b'', 'LONG.MD5':b'x'*256+b'\n',
           'MALFORM.MD5':b'not a checksum\n1234 ABC.BIN\n'+good,
           'MIXED.MD5':good+(b'12 invalid\n1Q invalid\n'*24)+good,
           'ABSENT.MD5':good.replace(b'ABC.BIN',b'NONE.BIN')}
    files['BIG.MD5']=hashlib.md5(files['BIG.BIN']).hexdigest().encode()+b'  BIG.BIN\n'
    def line(name,source=None):
        return b'MD5 ('+name.encode()+b') = '+hashlib.md5(files[source or name]).hexdigest().upper().encode()+b'\x9b'
    cases=[('ABC.BIN',line('ABC.BIN'),0,0),
           ('ABC.BIN EMPTY.BIN',line('ABC.BIN')+line('EMPTY.BIN'),0,0),
           ('A*.BIN',line('A*.BIN','ABC.BIN'),0,0),
           ('A?C.BIN',line('A?C.BIN','ABC.BIN'),0,0),
           ('A??.BIN',line('A??.BIN','ABC.BIN'),0,0),
           ('-P ABC.BIN',line('ABC.BIN'),0,0),
           ('+P ABC.BIN',b'',20,205),
           ('+H ABC.BIN',b'',20,205),
           ('+A ABC.BIN',b'',20,205),
           ('+S ABC.BIN',b'',20,156),
           ('NONE.BIN',b'',20,205),
           ('/H ABC.BIN',b'',20,156),('/Q ABC.BIN',b'',20,156)]
    cases += [('/C '+name+'.MD5',b'ABC.BIN: OK\x9b',0,0)
              for name in ('GOOD','ATARI','CRLF','FINAL','BSD','MALFORM')]
    cases += [('/C MIXED.MD5',b'ABC.BIN: OK\x9b'*2,0,0),
              ('/C BAD.MD5',b'ABC.BIN: \xc2\xc1\xc4\x9b',0,0),
              ('/C EMPTY.MD5',b'',0,0),('/C LONG.MD5',b'',20,137),
              ('/C ABSENT.MD5',b'NONE.BIN: ',20,205),
              ('/C NONE.MD5',b'',20,205)]
    return files,cases,line


def fixture(out, cancellation=False, metadata=False):
    binary=(ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes()
    (out/'audit.json').write_text(json.dumps(audit(binary),indent=2)+'\n')
    files,cases,line=corpus()
    if metadata:
        files.update({'PROT.BIN':b'protected','HIDDEN.BIN':b'hidden',
                      'ARCH.BIN':b'archived','BOTH.BIN':b'both','Q.BIN':b'padding'})
        cases=[('PROT.BIN',line('PROT.BIN'),0,0),
               ('+P PROT.BIN',line('PROT.BIN'),0,0),('-P PROT.BIN',b'',20,205),
               ('HIDDEN.BIN',b'',20,205),('+H HIDDEN.BIN',line('HIDDEN.BIN'),0,0),
               ('-H HIDDEN.BIN',b'',20,205),
               ('+A ARCH.BIN',line('ARCH.BIN'),0,0),('-A ARCH.BIN',b'',20,205),
               ('+AP BOTH.BIN',line('BOTH.BIN'),0,0),
               ('+P +A BOTH.BIN',line('BOTH.BIN'),0,0),
               ('+A -P BOTH.BIN',b'',20,205),
               ('+H -H HIDDEN.BIN',b'',20,205),
               ('Q???.BIN',line('Q???.BIN','Q.BIN'),0,0),
               ('+H H*.BIN',line('H*.BIN','HIDDEN.BIN'),0,0)]
    files={'MD5':binary,**files}
    payload=bytearray();setup=[];calls=[]
    def blob(raw):
        at=0x300000+len(payload);payload.extend(raw)
        return f'BYTE POINTER(ADDRESS(${at:x}))'
    for name,raw in files.items():
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),{blob(raw)},LONGINT(${len(raw):x}))')
    for i,(args,expected,primary,secondary) in enumerate(cases):
        calls.append(f'  Run({i},BYTE POINTER(c"{args}"),{len(args)},{blob(expected)},{len(expected)},{primary},{secondary})')
    first=blob(b'BIG.BIN: OK\x9b');second=blob(line('BIG.BIN'));recover=blob(line('ABC.BIN'))
    source=out/'probe.act'
    source.write_text((ROOT/'tests/programs/sdx_md5_acceptance.act').read_text()
        .replace('SHELL_INCLUDE',str(ROOT/'examples/shell/shell-session.inc'))
        .replace('SETUP_FILES','\n'.join(setup)).replace('RUN_CASES','\n'.join(calls))
        .replace('FIRST_EXPECTED',first).replace('SECOND_EXPECTED',second)
        .replace('SECOND_BYTES',str(len(line('BIG.BIN'))))
        .replace('RECOVER_EXPECTED',recover).replace('RECOVER_BYTES',str(len(line('ABC.BIN')))))
    if cancellation:
        text=source.read_text()
        extra=(ROOT/'tests/programs/sdx_md5_break.inc').read_text()
        uses=[line for line in extra.splitlines() if line.startswith('USE ')]
        extra='\n'.join(line for line in extra.splitlines() if not line.startswith('USE '))
        text=text.replace('USE EXEC', '\n'.join(uses)+'\nUSE EXEC',1)
        text=text.replace('PROC Main()',extra+'\nPROC Main()')
        start=text.index('  Run(0,');end=text.index('  Require(ShellFinish()',start)
        text=text[:start]+''.join(f'  BreakRun({mode})\n' for mode in range(4))+text[end:]
        source.write_text(text)
    if cancellation or metadata:
        from sdfs_reference import make
        directory=out/'files';directory.mkdir(exist_ok=True)
        for name in files:
            if name!='MD5':(directory/name).write_bytes(files[name])
        make(out/'input.atr',directory,1024,256,'MD5DATA')
        if metadata:
            from sdx_attribute_fixture import attributes
            flags=attributes(out/'input.atr',{'PROT.BIN':1,'HIDDEN.BIN':2,'ARCH.BIN':4,'BOTH.BIN':5})
            (out/'attributes.json').write_text(json.dumps(flags,indent=2)+'\n')
            source.write_text(source.read_text().replace('  Concurrent()\n',''))
    (out/'cases.json').write_text(json.dumps([dict(arguments=a,expected=e.hex(),primary=p,secondary=s)
        for a,e,p,s in cases],indent=2)+'\n')
    return source,[(0x300000,bytes(payload))]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    parser.add_argument('--breaks',action='store_true')
    parser.add_argument('--attributes',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running');started=time.monotonic()
    try:
        if not args.replay:source,payload=fixture(out,args.breaks,args.attributes)
        profile=out/'memory-profile.json'
        memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
        memory['image_data_bytes']=8192;profile.write_text(json.dumps(memory,indent=2)+'\n')
        mounts=[dict(alias='RAM',format=3)]
        disk=args.breaks or args.attributes
        if disk:mounts.append(dict(alias='DATA',unit=49,sectors=1024,sector_bytes=256,profile=4,format=2))
        program=read_build(out) if args.replay else build(compiler(ROOT/'build/actionc',release=True),source,out,
            tasks=True,task_capacity=8,console=True,console_test=True,sdx=True,
            image_data=payload,dos_mounts=mounts,memory_profile=profile,sdx_drive_a='DATA:' if disk else 'RAM:')
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            for key,value in PIN['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            if disk:
                media_before=hashlib.sha256((out/'input.atr').read_bytes()).hexdigest()
                b.config('diskemu','generic56k');b.mount(0,str(out/'input.atr'))
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:runtime,_=execute(b,program,timeout=240,frame_limit=12000)
            except Exception:
                print({k:data(b,program['image'],k) for k in ('checks','currentCase','primary','secondary','reason','actual','peer')},flush=True)
                if args.breaks:print({k:data(b,program['image'],k) for k in ('breakTicks','breakPC','breakPhase','pcSample','sampleCount')},flush=True)
                raise
            ownership(b,program,out)
            observed={k:int.from_bytes(bytes(data(b,program['image'],k)),'little') for k in ('checks','peer')}
            if args.breaks:
                observed.update({k:data(b,program['image'],k) for k in ('breakTicks','breakPC','breakPhase')})
        if disk:
            assert hashlib.sha256((out/'input.atr').read_bytes()).hexdigest()==media_before
            observed['media_sha256']=media_before
        result=dict(status='pass',tier='development',**observed,runtime=runtime,machine=machine,
            cases=json.loads((out/'cases.json').read_text()),build=program['build'])
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MD5 acceptance:',result['checks'],'checks passed',flush=True)


if __name__=='__main__':main()
