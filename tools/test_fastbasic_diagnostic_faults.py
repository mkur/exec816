#!/usr/bin/env python3
"""Compiler/diagnostic first-cause and allocation failures with real RAM files."""
import argparse,json,re,struct
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,read_build
from build_fastbasic import profile
from library_paths import read_source
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

def exhausted(raw,stem):
 """Fixture-only parser MEMTOP reduction at parser_alloc_init; real allocator."""
 raw=bytearray(raw);layout=profile(raw)
 labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.(\S+)',stem.with_suffix('.lbl').read_text())}
 bss=re.search(r'^BSS\s+([0-9A-F]+)\s+([0-9A-F]+)',stem.with_suffix('.map').read_text(),re.M)
 at=max(layout['end'],int(bss[2],16)+1 if bss else layout['end']);entry=labels['parser_alloc_init'];offset=entry-0x2ff0
 original=bytes(raw[offset:offset+3]);require(original[0]==0xa2 and original[2]==0xc8,'Parser allocation prologue')
 # AY=end of source. Set MEMTOP=end+256, preserving AY and original prologue.
 code=bytes.fromhex('8de50248c8988de60288')+bytes((0xa2,original[1],0xc8,0x68,0x60))
 require(at+len(code)<=labels['__HEAP_RUN__'],'Parser probe reaches compiler-owned heap')
 raw+=bytes(at-layout['end'])+code;raw[offset:offset+3]=b'\x20'+struct.pack('<H',at)
 struct.pack_into('<H',raw,10,at+len(code));return bytes(raw)

def run(out,reuse=False):
 out.mkdir(parents=True,exist_ok=True)
 (out/'fbdfault.act').write_text((ROOT/'tests/programs/fbdiagnostic_fault.act').read_text())
 for module in ('fbfiles','sdxfiles','fbdiagnostic'):
  text=read_source(ROOT/f'lib/dos/{module}.act').replace('USE DOS\n','USE DOS\nUSE FBDFAULT\n')
  for name in ('Open','Read','Write','Close'):text=text.replace('DOS.'+name+'(','FBDFAULT.'+name+'(')
  if module=='fbdiagnostic':text=text.replace('EXEC.AllocMem(','FBDFAULT.AllocMem(')
  (out/(module+'.act')).write_text(text)
 payload=bytearray();setup=[];calls=[];cases=[]
 def put(path,raw):
  at=0x300000+len(payload);payload.extend(raw);return f'  Put(BYTE POINTER(c"{path}"),BYTE POINTER(${at:x}),{len(raw)})'
 setup.append(put('RAM:SOURCE.BAS',b'? "FAULT RECOVERY"\x9b'))
 setup.append(put('RAM:BAD.BAS',b'???\x9b'))
 for name in ('FBCI','FBC'):
  raw=(ROOT/'build/fastbasic'/(name+'.COM')).read_bytes();setup.append(put('RAM:'+name+'.COM',raw))
  setup.append(put('RAM:'+name+'OOM.COM',exhausted(raw,ROOT/'build/fastbasic/source/build/bin'/name.lower())))
  for mode,error in ((1,221),(2,213),(3,221),(4,0),(5,221),(6,213),(7,205),(8,213),(9,213),(10,103),(0,0)):
   args='RAM:SOURCE.BAS RAM:FRESH.COM RAM:DIAG.DIA 12345678'
   calls.append(f'''  currentCase={len(cases)+1}
  FBDFAULT.mode={mode}
  Run(BYTE POINTER(c"RAM:{name}.COM"),BYTE POINTER(c"{args}"),{len(args)},{20 if error else 0})
  Require(secondary={error})''');cases.append(dict(compiler=name,mode=mode,cause=error))
  for source,dia,job,command,error in [('RAM:BAD.BAS','RAM:DIAG.DIA','12345678',name,306),('RAM:SOURCE.BAS','RAM:DIAG.DIA','00000000',name,115),('RAM:SOURCE.BAS','RAM:DIAG.DIA','BAD',name,115),('RAM:SOURCE.BAS','RAM:DIAG.DIA','12345678',name+'OOM',103)]:
   mode=5 if source=='RAM:BAD.BAS' else 0;args=f'{source} RAM:FRESH.COM {dia} {job}'
   calls.append(f'''  currentCase={len(cases)+1}
  FBDFAULT.mode={mode}
  Run(BYTE POINTER(c"RAM:{command}.COM"),BYTE POINTER(c"{args}"),{len(args)},20)
  Require(secondary={error})''');cases.append(dict(compiler=command,source=source,job=job,mode=mode,cause=error))
  calls.append('  FBDFAULT.mode=0\n  Run(BYTE POINTER(c"RAM:FRESH.COM"),NULL,0,0)')
 text=(ROOT/'tests/programs/fastbasic.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBDFAULT\n')
 text=text.replace('SETUP_FILES','\n'.join(setup)).replace('RUN_PROGRAMS','\n'.join(calls)).replace('EXTRA_CHECKS','')
 source=out/'probe.act';source.write_text(text);memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());memory['image_data_bytes']=32768
 mp=out/'memory-profile.json';mp.write_text(json.dumps(memory))
 p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,memory_profile=mp,dos_mounts=[dict(alias='RAM',format=3)],image_data=[(0x300000,bytes(payload))])
 with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
  machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
  try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
  except Exception:
   print({n:data(b,p['image'],n,True) for n in ('checks','currentCase','reason','primary','secondary')},flush=True);raise
  ownership(b,p,out);checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
 return dict(status='pass',tier='development',qualification=False,cases=cases,checks=checks,machine=machine,runtime=runtime,build=p['build'])
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--from-build',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
 try:r=run(out,args.from_build)
 except Exception as e:r.update(status='fail',error=str(e));raise
 finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
 print(r['checks'])
