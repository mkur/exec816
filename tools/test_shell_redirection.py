#!/usr/bin/env python3
"""Observe actual resident command output, including TYPE's writes to NIL."""
import argparse,json,shutil,hashlib,struct,time
from pathlib import Path
from native_program import ROOT,compiler,build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read as far_read
from test_shell_core import instrument,draw,collect_capture,HOOK,diagnostic_text
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
from test_console_display import terminal
from mydos_fixtures import Image
LOADED_SOURCE_SHA256=sha256(Path(__file__))
SCENARIOS=('basic','large','fault-read')
LIMITS=dict(host_seconds=1800,guest_frames=30000)

def convert(raw):return bytes(10 if x==155 else x if x in (9,10)or 32<=x<=126 else 46 for x in raw if x!=13)

def prepare(size,scenario):
    from test_shell_commands import prepare as base_prepare
    disk,_,derived,original=base_prepare(size,'fault-read' if scenario=='fault-read' else 'large' if scenario=='large' else 'raw-text')
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text());volume=next(v for v in manifest['volumes']if v['sector_bytes']==size)
    def file(name):
        f=next(f for f in volume['files']if f['path']==name)
        return bytes((i&255)^f['seed']for i in range(f['bytes']))
    def item(command,output=b'',error=0,source=None,kind='run',done=0):return dict(command=command,output=output,status=10 if error else 0,error=error,kind=kind,source=source,done=done)
    if scenario=='large':
        payload=file('LARGE.BIN');cases=[item('TYPE <LARGE.BIN >NIL:',convert(payload),source=payload),item('EXIT >NIL:',done=1)]
    elif scenario=='fault-read':cases=[item('TYPE <EXT.BIN >NIL:',diagnostic_text(213,'TYPE'),213),item('ECHO recovered >NIL:',b'recovered\n'),item('EXIT >NIL:',done=1)]
    else:
        text=file('TEXT.TXT');cases=[item('ECHO "<inside>" >NIL:',b'<inside>\n'),item('TYPE <D1:TEXT.TXT >NIL:',convert(text),source=text),
            item('TYPE <"D1:TEXT.TXT" > "NIL:"',convert(text),source=text),item('TYPE <NIL: >NIL:'),item('DIR TOOLS >NIL:',b'SUB/\n'),
            item('CD TOOLS >NIL:'),item('CD >NIL:',b'D1:TOOLS\n'),item('CD : >NIL:'),
            item('ECHO must-not-run <TEXT.TXT >TEXT.TXT',diagnostic_text(214,'Shell'),214),item('ECHO must-not-run <MISSING >NIL:',diagnostic_text(205,'Shell'),205),
            item('ECHO must-not-run >CONSOLE:',diagnostic_text(209,'Shell'),209),item('ECHO cooked >CON:',b'cooked\n'),item('TYPE <RAW: >NIL:',diagnostic_text(212,'TYPE'),212),item('ECHO raw >RAW:',b'raw\n')]
        for command in ('ECHO bad>NIL:','ECHO bad >','ECHO bad >>NIL:','ECHO bad >NIL: >RAW:','ECHO bad <NIL: <RAW:',
                        '<NIL:','EXIT extra >NIL:','CD TOOLS extra >NIL:','ECHO "bad*e" >NIL:','ECHO "x">NIL:','ECHO >NIL: <'):
            cases.append(item(command,diagnostic_text(115,'Shell'),115))
        cases += [item('UNKNOWN >RAW:',diagnostic_text(209,'Shell'),209),item('ECHO bad',b'bad'+diagnostic_text(206,'ECHO'),206,kind='missing')]
        cases += [item('TYPE <NIL: >NIL:')for _ in range(8)]
        cases += [item('EXIT >NIL:',done=1)]
    return disk,cases,derived,original

def run(t,out,mode,bank=1,size=128,scenario='basic'):
    out.mkdir(parents=True,exist_ok=True);source=instrument(out,'shell_redirection.act')
    observed=out/'shell-observed.inc'
    core=observed.read_text()
    hook_at=core.index('LONGCARD captureCount')
    core=core[:hook_at]+HOOK.replace('PROC ShellWrite(', 'PROC ObserveWrite(').replace('  NativeShellWrite(handle,bytes,count)\n','')
    require(core.count('  LET written=DOS.Write(')==1,'Missing shell write observer')
    core=core.replace('PROC NativeShellWrite(', 'PROC ShellWrite(').replace('  LET written=DOS.Write(', '  ObserveWrite(handle,bytes,count)\n  LET written=DOS.Write(')
    observed.write_text(core)
    capture_address=None
    command_address=0xf8000
    source.write_text(source.read_text().replace('$e0000','$f8000'))
    disk,cases,derived,original_sha=prepare(size,scenario);media=out/'volume.atr';media.write_bytes(disk.data);digest=sha256(media)
    blob=bytearray();calls=[]
    for case in cases:
        offset=len(blob);blob+=case['command'].encode()+b'\0';kind=case['kind']
        if kind=='run':calls.append(f'  Run({offset},{case["status"]},{case["error"]},{case["done"]})')
        else:calls.append(f'  MissingOutput({offset})')
    # A straight sequence of tiny dispatch helpers keeps generated fixed frames bounded.
    (out/'shell-redirection-cases.inc').write_text('PROC Cases()\n'+'\n'.join(calls)+'\nRETURN\n')
    p=build(t,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=disk.count,sector_bytes=size,profile=1)],
            image_data=[(command_address,bytes(blob))])
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned shell bridge')
    require(sha256(ROOT/'build/firmware/altirraos-816.rom')==PIN['rom']['sha256'],'Unpinned ROM')
    def at(name):return next(d['address']for d in p['image']['data']if '_SHELLAPP_'+name.upper()+'_'in d['name'])
    observations=[];saved={}
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower()if isinstance(v,bool)else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def before(b):
            nonlocal capture_address
            saved.update(screen=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['bytes']=b.memdump(saved['screen'],960)
            capture_address=collect_capture(b,p,out)
        original_regs=b.regs;last=time.monotonic()
        def regs():
            nonlocal last
            r=original_regs()
            if time.monotonic()-last>30:
                print('Command progress',scenario,'executed',b.peek16(at('executed')),'checks',b.peek16(at('checks')),'writes',b.peek16(at('captureCount')),'frame',b.eval_expr('@frame'),flush=True);last=time.monotonic()
            return r
        b.regs=regs
        try:rt,_=execute(b,p,before_run=before,timeout=LIMITS['host_seconds'],frame_limit=LIMITS['guest_frames'])
        except Exception:
            pointer=int.from_bytes(bytes(data(b,p['image'],'shell')),'little')
            print('Redirection checks/executed',data(b,p['image'],'checks',True),data(b,p['image'],'executed',True),'shell result',[b.eval_expr(f'dw(${pointer+i:x})')for i in (24,28,32,36,54)],flush=True);raise
        finally:b.regs=original_regs
        counts={k:int.from_bytes(bytes(data(b,p['image'],k)),'little')for k in ('captureCount','checks','executed')}
        require(data(b,p['image'],'stage')==[3]and counts['executed']==len(cases),'Incomplete commands')
        memory={};expected=bytearray(draw(b''))
        for case in cases:
            expected+=case['output']
        require(counts['captureCount']==len(expected),'Wrong command output length')
        actual=(out/'writes.bin').read_bytes();(out/'expected.bin').write_bytes(expected)
        require(actual==expected,'Actual command Write bytes differ');ownership(b,p,out)
        require(b.memdump(saved['screen'],960)==saved['bytes']and b.peek(752)==saved['cursor']and b.peek(16)==saved['mask'],'Console not restored')
        require(sha256(media)==digest,'Read-only fixture changed')
    commands=[]
    for c in cases:
        record={k:v for k,v in c.items()if k not in ('output','source')};record.update(output_bytes=len(c['output']),output_sha256=hashlib.sha256(c['output']).hexdigest())
        if c['source']is not None:record.update(source_bytes=len(c['source']),source_sha256=hashlib.sha256(c['source']).hexdigest())
        commands.append(record)
    return dict(status='pass',mode=mode,kernel_bank=bank,sector_bytes=size,scenario=scenario,build=p['build'],runtime=rt,machine=machine,pin=PIN,limits=LIMITS,counts=counts,commands=commands,memory=memory,observations=observations,derived=derived,
                capture_address=capture_address,command_address=command_address,fixture_sha256=sha256(source),writes_sha256=sha256(out/'writes.bin'),expected_sha256=sha256(out/'expected.bin'),media_sha256=digest,original_media_sha256=original_sha,hook_sha256=sha256(out/'shell-observed.inc'),
                source_inputs={s:LOADED_SOURCE_SHA256 if s=='tools/test_shell_redirection.py' else sha256(ROOT/s)for s in ('examples/shell/shell.act','examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tests/programs/shell_redirection.act','tools/test_shell_redirection.py','tools/test_shell_core.py','tools/test_shell_commands.py')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--bank',type=int,default=1);p.add_argument('--sector-size',type=int,default=128);p.add_argument('--scenario',choices=SCENARIOS,default='basic');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.bank,a.sector_size,a.scenario);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell redirection passed',a.case,a.scenario,a.bank,a.sector_size,flush=True)
