#!/usr/bin/env python3
"""WB4: emitted search, replacement, lexical and fold checks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out,reuse=False,raw=False):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/basic_assist.c',ROOT/'examples/gem-basic/document.c',
             ROOT/'examples/gem-basic/assist.c',ROOT/'c/calypsi/exec.c']
    if not reuse:
        f=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),True,
            roots=['BasicAssistProbe','BasicAssistChecks'],definitions={'assist.c':['-DAllocMem=BasicAssistAlloc']},source_optimization={'assist.c':not raw})
        (out/'c-image.json').write_text(json.dumps(f,indent=2)+'\n')
        source=out/'probe.act'
        source.write_text('MODULE BASICASSIST\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
            '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%f['symbols']['BasicAssistProbe'])
        p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
            task_capacity=8,foreign_image=f,optimize=True,console=False,stack_checks=True)
    else:p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text())
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',tier='development',qualification=False,slice='WB4',case='assistance',
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in sources},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
            report['machine']=verify_machine(b,rom,pin)
            try:runtime,_=execute(b,p,timeout=180,frame_limit=9000,timer_irq=True)
            except BaseException:
                for name in ('BasicAssistAllocationSize','BasicAssistAllocationFlags','BasicAssistAllocationResult','BasicAssistFree','BasicAssistSpan','BasicAssistSize','BasicAssistLength','BasicAssistFirst','BasicAssistLast','BasicAssistBytes'):
                    report['failure_'+name]=int.from_bytes(b.memdump(f['symbols'][name],4),'little')
                report['failure_checks']=b.peek16(f['symbols']['BasicAssistChecks'])
                report['failure_result']=data(b,p['image'],'result',True)
                report['failure_state']=list(b.memdump(0xa00,64))
                report['failure_registers']=b.regs()
                raise
            observed=data(b,p['image'],'result',True)
            if observed!=[0,0]:
                trace=b.memdump(f['symbols']['BasicAssistTrace'],320)
                report['failure_trace']=[[int.from_bytes(trace[(r*8+c)*4:(r*8+c+1)*4],'little') for c in range(8)] for r in range(10)]
                where=f['symbols']['d'];raw=b.memdump(where,46)
                u=lambda at:int.from_bytes(raw[at:at+4],'little')
                for name in ('BasicAssistAllocationSize','BasicAssistAllocationFlags','BasicAssistAllocationResult','BasicAssistFree','BasicAssistSpan','BasicAssistSize','BasicAssistLength','BasicAssistFirst','BasicAssistLast','BasicAssistBytes'):
                    report['failure_'+name]=int.from_bytes(b.memdump(f['symbols'][name],4),'little')
                report['failure_checks']=b.peek16(f['symbols']['BasicAssistChecks'])
                report['failure_last_result']=b.peek16(f['symbols']['BasicAssistLastResult'])
                report['failure_last_count']=int.from_bytes(b.memdump(f['symbols']['BasicAssistLastCount'],4),'little')
                report['failure_document']=dict(gap=u(12),end=u(16),bytes=u(20),
                    source=(b.memdump(u(0),u(12))+b.memdump(u(0)+u(16),32768-u(16))).hex())
            require(observed==[0,0],'Assistance assertion line: '+str(observed))
            ownership(b,p,p['output'])
            report.update(status='pass',runtime=runtime,checks=b.peek16(f['symbols']['BasicAssistChecks']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true');p.add_argument('--raw-assist',action='store_true');a=p.parse_args();run(a.output.resolve(),a.from_build,a.raw_assist)
