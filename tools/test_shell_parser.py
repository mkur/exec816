#!/usr/bin/env python3
"""Emitted parser edge cases, including bytes absent from the physical keymap."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,build,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
FIXTURE_ADDRESS=0x30e000
CASES=[('',0,[]),('   ',0,[]),('help',1,['help']),('HELP',1,['HELP']),('"echo" "" x',2,['echo','','x']),
       ('echo "hello world"',2,['echo','hello world']),('echo "a**b*"c"',2,['echo','a*b"c']),
       ('echo a*b',2,['echo','a*b']),('echo `literal`',2,['echo','`literal`']),
       ('echo "< > | ;"',2,['echo','< > | ;']),('echo   x   y ',2,['echo','x','y']),
       ('cd ""',3,['cd','']),('cd /',3,['cd','/']),('cd ..',3,['cd','..']),('exit',4,['exit']),
       ('execute file',20,['execute','file']),('ExEcUtE "SYS:FILE"',20,['ExEcUtE','SYS:FILE']),
       ('cls',16,['cls']),('CLS',16,['CLS']),
       ('tasks',8,['tasks']),('TASKS',8,['TASKS']),('ver',9,['ver']),('VER',9,['VER']),
       ('mount',10,['mount']),('MoUnT',10,['MoUnT']),('devices',11,['devices']),('DEVICES',11,['DEVICES']),
       ('echo '+' '.join(['x']*15),2,['echo']+['x']*15),('echo '+'x'*250,2,['echo','x'*250])]
CASES += [(s,None,None) for s in ('echo '+' '.join(['x']*16),'echo "unterminated','echo "bad*"','echo "bad*x"','echo pre"word"','echo "word"post','echo one|two','echo one;two','echo>>NIL:','echo a>NIL:','help extra','cls extra','exit extra','tasks extra','ver extra','mount D2:','devices extra','cd one two','EXECUTE','EXECUTE ""','EXECUTE one two','EXECUTE FILE|WC','HELLO|EXECUTE FILE')]

CASES += [(s,12,[s]) for s in ('mounts','device','unknown','HELLO','D1:TOOLS/HELLO')]
CASES += [('ECHOARGS \"two words\" \"\" >NIL: x',12,['ECHOARGS','two words','','x'])]
CAT_ARGUMENTS={'CAT\t"A** B"\t>NIL:':'A* B', 'CAT "a*\"b"':'a"b', 'CAT\tfoo\t':'foo'}
CASES += [(source,12,['CAT',decoded]) for source,decoded in CAT_ARGUMENTS.items()]
TAILS={'ECHOARGS \"two words\" \"\" >NIL: x':'\"two words\" \"\" x'}

APPENDS={
    'echo >>WORK:LOG.TXT': ['echo'],
    'echo >> WORK:LOG.TXT x': ['echo','x'],
    '>>"WORK:LOG.TXT" echo "two words"': ['echo','two words'],
    'echo x <NIL: >>WORK:LOG.TXT': ['echo','x'],
    'echo '+' '.join(['x']*13)+' <NIL: >>WORK:LOG.TXT': ['echo']+['x']*13,
}
CASES += [(source,2,words) for source,words in APPENDS.items()]
CASES += [('echo "a >> b"',2,['echo','a >> b'])]
TAILS['echo >> WORK:LOG.TXT x']='x'
CASES += [(source,None,None) for source in (
    'echo >>','echo >>>WORK:LOG.TXT','echo > >WORK:LOG.TXT',
    'echo >>WORK:LOG.TXT >NIL:','echo >NIL: >>WORK:LOG.TXT',
    'echo >>WORK:LOG.TXT >>WORK:OTHER.TXT','>>WORK:LOG.TXT',
    'echo '+' '.join(['x']*14)+' <NIL: >>WORK:LOG.TXT')]

REDIRECTS={'CAT\t"A** B"\t>NIL:':(None,'NIL:'),'ECHOARGS \"two words\" \"\" >NIL: x':(None,'NIL:'),'echo >NIL:':(None,'NIL:'),'echo <NIL:':('NIL:',None),
    'CLS >NIL:':(None,'NIL:'),
    '<"D1:TEXT.TXT" echo "x" > NIL:':('D1:TEXT.TXT','NIL:'),
    'echo '+' '.join(['x']*13)+' <NIL: >RAW:':('NIL:','RAW:')}
REDIRECTS.update({source:('NIL:' if '<NIL:' in source else None,'WORK:LOG.TXT')
                  for source in APPENDS})
CASES += [('echo >NIL:',2,['echo']),('echo <NIL:',2,['echo']),
    ('CLS >NIL:',16,['CLS']),
    ('<"D1:TEXT.TXT" echo "x" > NIL:',2,['echo','x']),
    ('echo '+' '.join(['x']*13)+' <NIL: >RAW:',2,['echo']+['x']*13),
    ('echo '+' '.join(['x']*14)+' <NIL: >RAW:',None,None)]

PIPELINES={
    'HELLO|WC':(1,'',''),
    ' CAT "STORY.TXT" | WC ':(2,'"STORY.TXT"',''),
    'CAT <STORY.TXT|WC >NIL:':(1,'',''),
    'CAT <STORY.TXT|WC >>WORK:LOG.TXT':(1,'',''),
    'LEFT "a|b" x|RIGHT "" y':(3,'"a|b" x','"" y'),
    'LEFT '+'x'*243+'|RIGHT':(2,'x'*243,''),
}
CASES += [
    ('HELLO|WC',12,['HELLO','WC']),
    (' CAT "STORY.TXT" | WC ',12,['CAT','STORY.TXT','WC']),
    ('CAT <STORY.TXT|WC >NIL:',12,['CAT','WC']),
    ('CAT <STORY.TXT|WC >>WORK:LOG.TXT',12,['CAT','WC']),
    ('LEFT "a|b" x|RIGHT "" y',12,['LEFT','a|b','x','RIGHT','','y']),
    ('LEFT '+'x'*243+'|RIGHT',12,['LEFT','x'*243,'RIGHT']),
]
REDIRECTS['CAT <STORY.TXT|WC >NIL:']=('STORY.TXT','NIL:')
APPENDS['CAT <STORY.TXT|WC >>WORK:LOG.TXT']=['CAT','WC']
REDIRECTS['CAT <STORY.TXT|WC >>WORK:LOG.TXT']=('STORY.TXT','WORK:LOG.TXT')
CASES += [(s,None,None) for s in (
    '|WC','HELLO|','HELLO||WC','HELLO | | WC','HELLO|WC|CAT',
    'HELP|WC','CLS|WC','HELLO|CLS','HELLO|TYPE','HELLO >NIL:|WC','CAT|WC <NIL:',
    '""|WC','HELLO|""','CAT <|WC','CAT|WC >','HELLO >>WORK:LOG.TXT|WC',
    'LEFT '+' '.join(['x']*15)+'|RIGHT')]

def run(t,out,mode):
    out.mkdir(parents=True,exist_ok=True);blob=bytearray();calls=[];checks=2
    def text(value):
        offset=len(blob);blob.extend(value.encode()+b'\0');return offset
    for source,command,words in CASES:
        calls.append(f'  Parse({text(source)},{int(command is not None)},{command or 0},{len(words or [])})');checks+=1
        if command is not None:
            checks+=1
            calls.append(f'  Check(shell.outputAppend={int(source in APPENDS)})');checks+=1
            if source in CAT_ARGUMENTS:
                calls.append(f'  CatArgument({text(CAT_ARGUMENTS[source])})');checks+=1
            if source in TAILS:
                calls.append(f'  Tail({text(TAILS[source])})');checks+=1
            if source in PIPELINES:
                boundary,left,right=PIPELINES[source]
                calls.append(f'  CheckPipeline({boundary},{text(left)},{text(right)})');checks+=3
            else:
                calls.append('  Check(shell.pipeline=0)');checks+=1
            targets=REDIRECTS.get(source,(None,None))
            for side,target in enumerate(targets):
                calls.append(f'  Redirect({side},{text(target)if target is not None else 65535})');checks+=1
            for index,word in enumerate(words):calls.append(f'  Word({index},{text(word)})');checks+=1
    (out/'shell-parser-cases.inc').write_text('PROC Cases()\n'+'\n'.join(calls)+'\nRETURN\n')
    (out/'shell_parser.act').write_text((ROOT/'tests/programs/shell_parser.act').read_text().replace('../../examples/shell/shell-session.inc',str(ROOT/'examples/shell/shell-session.inc')).replace('$e0000',f'${FIXTURE_ADDRESS:x}'))
    # The shared session brings in the shell's globals and fault strings;
    # match the demo's 4 KiB upper-RAM arena without starting a console Task.
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    memory=out/'memory-profile.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    # Raw resident code now reaches the old $0e0000 fixture location. Keep the
    # byte oracle in a free upper bank, independent of emission size.
    p=build(t,out/'shell_parser.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=False,console_deferred=True,dos_mounts=[],memory_profile=memory,image_data=[(FIXTURE_ADDRESS,bytes(blob))])
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console bridge')
    require(sha256(ROOT/'build/firmware/altirraos-816.rom')==PIN['rom']['sha256'],'Unpinned ROM')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:rt,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:print('Parser checks/cases',data(b,p['image'],'checks',True),data(b,p['image'],'caseCount',True),flush=True);raise
        require(data(b,p['image'],'finished')==[1] and data(b,p['image'],'checks',True)==[checks] and data(b,p['image'],'caseCount',True)==[len(CASES)],'Incomplete parser cases')
        require(rt['created']==0,'Parser created a worker');ownership(b,p,out)
    return dict(status='pass',mode=mode,build=p['build'],runtime=rt,machine=machine,pin=PIN,checks=checks,cases=CASES,fixture_sha256=sha256(out/'shell-parser-cases.inc'),source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','examples/shell/shell-redirection.inc','tests/programs/shell_parser.act','tools/test_shell_parser.py')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell parser passed',a.case,flush=True)
