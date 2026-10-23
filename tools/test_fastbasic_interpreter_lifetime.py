#!/usr/bin/env python3
"""Source engines: two guests, peer progress, SDX, relaunch and bounded BREAK."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from build_fastbasic import sha256
from native_program import ROOT,build,compiler,read_build,require,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership
from test_sdx_md5 import PIN


def run(out,floating=False,probe=0,replay=False,decimal=False):
    out.mkdir(parents=True,exist_ok=True)
    engine='FB' if floating else 'FBI'
    raw=(ROOT/f'build/fastbasic/{engine}.COM').read_bytes()
    injection=None
    if decimal:
        require(floating,'Decimal probe requires the FP engine')
        from test_fastbasic import decimal_nmi_probe
        path=out/'FB.COM';path.write_bytes(raw)
        for suffix in ('.map','.lbl'):shutil.copyfile(ROOT/f'build/fastbasic/source/build/bin/fbrun{suffix}',path.with_suffix(suffix))
        injection=decimal_nmi_probe(path);raw=path.read_bytes()
    files={engine+'.COM':raw,
        'MD5.COM':(ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes(),'ABC.TXT':b'abc'}
    from test_sdx_arc import archive
    files.update({p.name:p.read_bytes() for p in (ROOT/'build/sdx-inputs/arc').glob('*') if p.suffix in ('.COM','.OVL')})
    files['SAMPLE.ARC']=archive({'ITEM.TXT':b'abc'})
    for filename,donor in [('WORKER','fp_worker' if floating else 'worker'),
            ('SECOND','fp_second' if floating else 'worker'),('BUSY','fp_busy' if floating else 'busy')]:
        files[filename+'.BAS']=(ROOT/f'tests/fastbasic/{donor}.bas').read_bytes()
        if decimal and filename!='BUSY':files[filename+'.BAS']=b'I=3\nZ%=I\n'+files[filename+'.BAS']
    payload=bytearray();setup=[]
    for name,raw in files.items():
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(${0x300000+len(payload):x}),{len(raw)})')
        payload+=raw
    text=(ROOT/'tests/programs/fastbasic_lifetime.act').read_text()
    arc='''  LET arcOutput=DOS.Open(BYTE POINTER(c"RAM:ARC.TXT"),DOS.MODE_NEWFILE)
  Require(arcOutput<>NULL)
  DOS.SelectOutput(arcOutput)
  LET arc=PROGRAMFILE.Load(BYTE POINTER(c"RAM:ARC.COM"))
  Require(arc<>NULL)
  secondId=PROCESS.StartBackgroundLoaded(BYTE POINTER(arc),BYTE POINTER(c"L SAMPLE.ARC"),12)
  Require(secondId<>0)
  Wait(secondId,0)
  PROGRAM.Unload(arc)
  Require(DOS.Close(arcOutput)<>0)
  DOS.SelectOutput(output1)
'''
    text=text.replace('SETUP_FILES','\n'.join(setup)).replace('FLOAT_COMPILER_RUN',arc)
    text=text.replace('USE FBSTATE','USE FBITIMING\nUSE FBSTATE')
    text=text.replace('USE DOS\n','USE DOS\nUSE DOSDELAY\n')
    text=text.replace('CARD checks,','LONGCARD ARRAY holders(10)\nCARD holderIndex,breakObservation\nCARD checks,')
    text=text.replace('PROC Main()', '''PUBLIC LONGINT FUNC HolderEntry()

  WHILE DOS.BreakPending()=0 DO
    DOSDELAY.Delay(50)
  OD
  DOS.SetIoErr(0)

RETURN(0)

PROC Main()''')
    text=text.replace('  currentCase=2','''  FOR holderIndex=0 TO 9 DO
    holders(holderIndex)=PROCESS.StartBackground(@HolderEntry,NULL,0)
    Require(holders(holderIndex)<>0)
  OD
  currentCase=2''')
    text=text.replace('  LET state=FBSTATE.Session POINTER(busy.extension)','''  LET state=FBSTATE.Session POINTER(busy.extension)
  Require(PROCESS.StartBackgroundLoaded(BYTE POINTER(busy),NULL,0)=0)
  Require(DOS.IoErr()=103)
  FOR holderIndex=4 TO 9 DO
    Require(PROCESS.RequestBreak(holders(holderIndex))<>0)
    Wait(holders(holderIndex),0)
  OD''')
    text=text.replace('  PROGRAM.Unload(busy)','''  PROGRAM.Unload(busy)
  FOR holderIndex=0 TO 3 DO
    Require(PROCESS.RequestBreak(holders(holderIndex))<>0)
    Wait(holders(holderIndex),0)
  OD''')
    text=text.replace('  Require(breakTicks<=2)','''  Require(FBITIMING.seen<>0)
  breakObservation=FBITIMING.observed-started
  Require(breakObservation<=2)
  Require(breakTicks<=10)''')
    text=text.replace('DOS.Read(file,@actual,128)=21','DOS.Read(file,@actual,128)>=21')
    if injection:
        text=text.replace('  PROGRAM.Unload(second)',f'  Require(one.guest.bank(${injection["marker"]:x})=1)\n  Require(two.guest.bank(${injection["marker"]:x})=1)\n  PROGRAM.Unload(second)')
    for name in ('WORKER','SECOND_GUEST','BUSY'):
        text=text.replace(f'RAM:{name}.COM',f'RAM:{engine}.COM')
    for var,name in [('first','WORKER'),('second','SECOND'),('busy','BUSY')]:
        arg='RAM:'+name+'.BAS'
        text=text.replace(f'StartBackgroundLoaded(BYTE POINTER({var}),NULL,0)',
            f'StartBackgroundLoaded(BYTE POINTER({var}),BYTE POINTER(c"{arg}"),{len(arg)})')
    source=out/'probe.act';source.write_text(text)
    timing=out/'fbitiming.act';timing.write_text((ROOT/'tests/programs/fbitiming.act').read_text())
    service=out/'fbservice.act'
    service.write_text((ROOT/'lib/dos/fbservice.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBITIMING\n')
        .replace('      cause=DOS.ERROR_BREAK','      FBITIMING.Mark()\n      cause=DOS.ERROR_BREAK'))
    memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());memory['image_data_bytes']=16384
    mp=out/'memory-profile.json';mp.write_text(json.dumps(memory))
    p=read_build(out) if replay else build(compiler(ROOT/'build/actionc',release=True),source,out,
        tasks=True,task_capacity=12,console=False,console_test=True,sdx=True,sdx_return_probe=probe,
        memory_profile=mp,image_data=[(0x300000,bytes(payload))],dos_mounts=[dict(alias='RAM',format=3)])
    result=dict(status='running',tier='development',floating=floating,return_probe=probe,decimal_probe=injection,
        inputs={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},build=p['build'],
        local_overrides={p.name:sha256(p) for p in (timing,service)})
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        result['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:result['runtime'],_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print({n:data(b,p['image'],n,True) for n in ('checks','currentCase','primary','secondary','reason','breakTicks')},flush=True)
            raise
        ownership(b,p,out)
        for name in ('checks','breakTicks','breakObservation','firstProgress','secondProgress'):
            result[name]=int.from_bytes(bytes(data(b,p['image'],name)),'little')
        actual=bytes(data(b,p['image'],'actual'))
        require(actual[:21]==b'WORKER\x9b'*3,repr(actual[:21]))
        answer=b'WORKER\x9bMD5 (ABC.TXT) = '+hashlib.md5(b'abc').hexdigest().upper().encode()+b'\x9b'
        require(actual[32:32+len(answer)]==answer,repr(actual[32:]))
    result['status']='pass'
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--float',dest='floating',action='store_true')
    a.add_argument('--return-probe',type=int,choices=(0,7),default=0);a.add_argument('--replay',action='store_true');a.add_argument('--decimal',action='store_true');args=a.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.floating,args.return_probe,args.replay,args.decimal)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Source lifetime:',r['checks'],'checks; BREAK',r['breakTicks'],'ticks')
