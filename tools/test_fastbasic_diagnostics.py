#!/usr/bin/env python3
"""Exercise compiler-owned diagnostic files through emitted Exec code."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,read_build
from build_fastbasic import sha256
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

CASES=[('first',b'???\x9b',2),('last',b'? 1\x9b???\x9b',2),
 ('tab',b'\t???\x9b',2),('statement',b'? 1: ???\x9b',2),
 ('unterminated',b'? 1',4),('empty',b'',4),
 ('crlf',b'? 1\r\n? 2\r\n',4),('longline',b'? '+b'1'*260+b'\x9b',2),
 ('badbyte',b'? 1\x00\x9b',2),('oversize',b"'"+b'x'*40000,1)]

def run(out,reuse=False):
 out.mkdir(parents=True,exist_ok=True)
 payload=bytearray();setup=[];calls=[];observations=[];index=0;stored={}
 def put(path,raw):
  address=0x300000+len(payload);payload.extend(raw or b'\0')
  setup.append(f'  Put(BYTE POINTER(c"{path}"),BYTE POINTER(${address:x}),{len(raw)})')
 for compiler_name in ('FBCI','FBC'):
  put('RAM:'+compiler_name+'.COM',(ROOT/'build/fastbasic'/ (compiler_name+'.COM')).read_bytes())
  for name,source,stage in CASES:
   index+=1;src=f'RAM:S{index}.BAS';dia=f'RAM:D{index}.DIA';dest=f'RAM:C{index}.COM'
   if source in stored:src=stored[source]
   else:put(src,source);stored[source]=src
   args=f'{src} {dest} {dia} {index:08X}'
   calls.append(f'''  currentCase={index}
  Run(BYTE POINTER(c"RAM:{compiler_name}.COM"),BYTE POINTER(c"{args}"),{len(args)},{0 if stage==4 else 20})
  LET diagnostic{index}=DOS.Open(BYTE POINTER(c"{dia}"),DOS.MODE_OLDFILE)
  Require(diagnostic{index}<>NULL)
  Require(DOS.Read(diagnostic{index},BYTE POINTER(@records)+{(index-1)*224},224)=224)
  Require(DOS.Close(diagnostic{index})<>0)''')
   observations.append(dict(index=index,name=name,compiler=compiler_name,source=src,stage=stage))
 text=(ROOT/'tests/programs/fastbasic.act').read_text().replace('CARD checks,','BYTE ARRAY records(4480)\nCARD checks,')
 text=text.replace('SETUP_FILES','\n'.join(setup)).replace('RUN_PROGRAMS','\n'.join(calls)).replace('EXTRA_CHECKS','')
 path=out/'probe.act';path.write_text(text)
 memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());memory['image_data_bytes']=len(payload)+8
 mp=out/'memory-profile.json';mp.write_text(json.dumps(memory))
 p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),path,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,
   memory_profile=mp,dos_mounts=[dict(alias='RAM',format=3)],image_data=[(0x300000,bytes(payload))])
 with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
  machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
  try: runtime,_=execute(b,p,timeout=240,frame_limit=12000)
  except Exception:
   print({n:data(b,p['image'],n,True) for n in ('checks','currentCase','reason','primary','secondary')},flush=True);raise
  ownership(b,p,out);raw=bytes(data(b,p['image'],'records'))
  for item in observations:
   r=raw[(item['index']-1)*224:item['index']*224]
   magic,version,size,job,stage,basic,cause,line,column,ns,nm,reserved=struct.unpack('<4sHHIHH iIHHHH',r[:32])
   require((magic,version,size,job,stage,reserved)==(b'FBD1',1,224,item['index'],item['stage'],0),repr((item,r[:32].hex())))
   require(r[32:32+ns].decode()==item['source'],'Source identity')
   require(0<nm<64 and r[160+nm]==0,'Message bounds')
   require((cause==0)==(stage==4),'First native cause')
   expected={'first':(1,1),'last':(2,1),'tab':(1,2),'statement':(1,6),
     'longline':(1,255),'badbyte':(1,3)}.get(item['name'],(0,0))
   require((line,column)==expected,'Independent byte location: '+repr((item,line,column,expected)))
   item.update(basic_error=basic,cause=cause,line=line,column=column,message=r[160:160+nm].decode('ascii'),sha256=__import__('hashlib').sha256(r).hexdigest())
  checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
 return dict(status='pass',tier='development',qualification=False,checks=checks,cases=observations,machine=machine,runtime=runtime,
  build=p['build'],compilers={n:sha256(ROOT/'build/fastbasic'/(n+'.COM')) for n in ('FBCI','FBC')})

if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--from-build',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'build/fastbasic-workbench/wb8-diagnostics');args=a.parse_args()
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
 try:result=run(out,args.from_build)
 except Exception as e:result.update(status='fail',error=str(e));raise
 finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 print('Diagnostic checks:',result['checks']);print(json.dumps(result['cases'],indent=2))
