#!/usr/bin/env python3
"""Primes sieve, padded numeric fields, skipped writes and cooperative stop."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(out,compiler_dir,reuse=False):
 out.mkdir(parents=True,exist_ok=True)
 source=ROOT/'examples/commands/primes.act'
 text=source.read_text().replace('USE COMMAND','USE PROGRAMAPI AS COMMAND').replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR')
 for prefix in ('BYTE ARRAY composite','CARD ARRAY dimensions','ADDRESS ARRAY values','BYTE POINTER pane','CARD candidate','LONGCARD pass','BYTE FUNC Paint','BYTE FUNC Labels','LONGINT FUNC Main'):
  text=text.replace(prefix,'PUBLIC '+prefix)
 if reuse:require((out/'primes.act').read_text()==text,'Changed replay calculation')
 (out/'primes.act').write_text(text)
 api=(ROOT/'lib/dos/programapi.act').read_text().replace('; Explicit task-only providers.','INCLUDE "command-results.inc"\nINCLUDE "command-errors.inc"\nINCLUDE "command-args.inc"\nPUBLIC LONGCARD numericCalls,numericBytes\n; Explicit task-only providers.')
 api=api.replace('RETURN(DOSCALLS.WriteAt(handle,column,row,buffer,length))','  IF column=10 THEN\n    numericCalls==+1\n    numericBytes==+LONGCARD(length)\n  FI\n\nRETURN(DOSCALLS.WriteAt(handle,column,row,buffer,length))')
 for name in ('command-results.inc','command-errors.inc','command-args.inc'):
  (out/name).write_bytes((ROOT/'lib/dos'/name).read_bytes())
 if reuse:require((out/'programapi.act').read_text()==api,'Changed replay provider observer')
 (out/'programapi.act').write_text(api)
 local=out/'primes_fields.act';local.write_bytes((ROOT/'tests/programs/primes_fields.act').read_bytes())
 profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
 profile['image_data_bytes']=4096
 (out/'memory.json').write_text(json.dumps(profile))
 p=read_build(out) if reuse else build(compiler(compiler_dir),local,out,optimize=True,tasks=True,task_capacity=8,console=True,memory_profile=out/'memory.json')
 require(p['build']['source_sha256']==sha256(local),'Changed replay fixture')
 pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
 with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
  for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
  machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
  try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
  except Exception:
   print('Primes checks',data(b,p['image'],'checks',True),flush=True);raise
  require(data(b,p['image'],'finished')==[1],'Primes fixture incomplete')
  ownership(b,p,out)
 return dict(status='pass',tier='development',build=p['build'],runtime=runtime,machine=machine,source_sha256=sha256(source),bank_zero_delta=dict(fixed=0,per_task=0))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reuse',action='store_true');parser.add_argument('--compiler-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
 r=run(a.output.resolve(),a.compiler_dir,a.reuse);(a.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Primes field checks passed')
