#!/usr/bin/env python3
"""Actual toolbox command bodies and resident helpers on controlled native streams."""
import argparse
import json
import struct
import subprocess
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
NAMES = ('cmp', 'cksum', 'hexdump', 'head', 'tail', 'grep', 'list', 'more', 'cat', 'wc', 'hello')
STRIDE = 4372


def behavior_vectors(name):
    def c(label, payload=b'', args=b'', expected=b'', **kw):
        return dict(name=label, payload=payload, args=args, expected=expected, **kw)
    if name in ('cat','wc','hello'):
        return []
    common = [c('read-error', b'x\n', readFail=1, error=226),
              c('partial-read-error', b'x\n', prefixError=226, error=226),
              c('break', b'x\n', breakAt=0, error=304),
              c('missing', args=b'MISSING', error=205)]
    if name == 'cmp':
        return [c('equal', b'a\0\xff', b'A B', other=b'a\0\xff', opens=2),
                c('empty', args=b'A B', opens=2),
                c('different', b'ab', b'A B', b'Different at byte 1\n', other=b'ac', status=5, opens=2),
                c('shorter', b'ab', b'A B', b'Different at byte 1\n', other=b'a', status=5, opens=2),
                c('wide', b'x', b'A B', length=65537, other=b'x', otherLength=65537, opens=2),
                c('second-open-failure', b'a', b'A MISSING', error=205, opens=1),
                c('read-error', b'a', b'A B', other=b'a', readFail=1, error=226, opens=2),
                c('close-error', b'a', b'A B', other=b'a', closeError=202, error=202, opens=2)]
    if name == 'cksum':
        cases = [c('empty'), c('binary', bytes(range(256))), c('known', b'123456789'),
                 c('partial', b'abc\n', chunk=1, writeChunk=2), c('wide', b'x', length=65537)]
        for case in cases:
            payload = case['payload']; length=case.get('length',len(payload))
            whole=(payload*((length+len(payload)-1)//len(payload)))[:length] if payload else b''
            case['expected']=subprocess.check_output(['cksum'],input=whole)
        return cases+common+[c('write-error', b'x', writeFail=1,error=214)]
    if name == 'hexdump':
        cases=[c('empty'), c('binary',bytes(range(33))),
               c('range',bytes(range(33)),b'OFFSET 15 LENGTH 3'),
               c('zero',b'abc',b'LENGTH 0'),c('beyond',b'abc',b'OFFSET 4')]
        for case in cases:
            start,limit=(15,3) if case['name']=='range' else (4,99) if case['name']=='beyond' else (0,0) if case['name']=='zero' else (0,99)
            payload=case['payload'][start:start+limit]
            case['expected']=b''.join((f'{start+i:08X}  '+''.join(f'{b:02X} ' for b in payload[i:i+16]).ljust(48)+' |'+''.join(chr(b) if 32<=b<=126 else '.' for b in payload[i:i+16])+'|\n').encode() for i in range(0,len(payload),16))
        return cases+common+[c('bad-number',args=b'LENGTH -1',error=115)]
    if name == 'head':
        common[1]['expected']=b'x\n'
        return [c('mixed',b'a\r\nb\rc\nd\x9be',expected=b'a\nb\nc\nd\ne',chunk=1),
                c('two',b'a\nb\nc\n',b'LINES 2',b'a\nb\n'),
                c('zero',b'a\n',b'LINES 0'),c('empty'),
                c('nul',b'a\0b\n',expected=b'a\0b\n'),
                c('exact-line',b'x'*1024+b'\n',expected=b'x'*1024+b'\n'),
                c('long-line',b'x'*1025,error=120),
                c('max-number',b'x',b'LINES=4294967295',b'x'),
                c('partial',b'hello\n',expected=b'hello\n',writeChunk=2),
                c('early-prefix-error',b'x\n',b'LINES 1',b'x\n',prefixError=226,error=226),
                c('syntax-diagnostic',args=b'LINES -1',interactive=1,error=115,opens=1,consoleExpected=b'Arguments: FILE,LINES/K/N\n'),
                c('zero-write',b'x\n',writeChunk=0,error=206)]+common
    if name == 'tail':
        sequence=b''.join(f'{i}\n'.encode() for i in range(20))
        return [c('empty'),c('short',b'a\nb\n',expected=b'a\nb\n'),
                c('default-wrap',sequence,expected=b''.join(f'{i}\n'.encode() for i in range(10,20))),
                c('one',sequence,b'LINES 1',b'19\n'),
                c('maximum',sequence,b'LINES 16',b''.join(f'{i}\n'.encode() for i in range(4,20))),
                c('zero',b'a\n',b'LINES 0',noReads=True),
                c('mixed',b'a\r\nb\rc\nd\x9be',b'LINES 3',b'c\nd\ne',chunk=1),
                c('unterminated',b'a\nb',b'LINES 1',b'b'),
                c('blank',b'a\n\nb\n\n',b'LINES 3',b'\nb\n\n'),
                c('nul',b'a\0b\n',expected=b'a\0b\n'),
                c('exact-line',b'x'*1024+b'\n',expected=b'x'*1024+b'\n'),
                c('long-line',b'x'*1025,error=120),
                c('named',b'a\nb\n',b'A LINES 1',b'b\n',opens=1),
                c('empty-name',args=b'""',error=210),
                c('too-many-lines',args=b'LINES 17',error=115,noReads=True),
                c('max-number',args=b'LINES=4294967295',error=115,noReads=True),
                c('partial-write',b'ab\ncd\n',b'LINES 1',b'cd\n',writeChunk=1),
                c('write-error',b'x\n',writeFail=1,error=214),
                c('zero-write',b'x\n',writeChunk=0,error=206),
                c('close-error',b'x\n',b'A',b'x\n',closeError=202,error=202,opens=1),
                c('read-close-errors',b'x\n',b'A',readFail=1,closeError=202,error=226,opens=1),
                c('wide',b'x\n',length=65538,expected=b'x\n'*10)]+common
    if name == 'grep':
        cases=[c('literal',b'a.c\nabc\n',b'"a.c"',b'a.c\n'),
               c('fold-number',b'Ab\r\nxx\x9bab',b'ab NOCASE NUMBER',b'1:Ab\n3:ab',chunk=1),
               c('invert',b'ab\nxx\n',b'ab INVERT',b'xx\n'),
               c('none',b'abc\n',b'xyz',status=5),
               c('empty',args=b'x',status=5),
               c('empty-pattern',b'\nA\n',b'""',b'\nA\n'),
               c('nul',b'\0abc\n',b'abc',b'\0abc\n'),
               c('long-line',b'x'*1025,b'x',error=120)]
        for case in common:
            case['args']=b'x '+case['args']
        common[1]['expected']=b'x\n'
        return cases+common
    if name == 'list':
        return [c('empty',opens=1),c('mixed',expected=b'A 1\nB/\nC 3\n',entries=3,opens=1),
                c('names',args=b'NAMES',expected=b'A\nB\n',entries=2,opens=1),
                c('enumeration-error',error=226,enumerationError=226,opens=1),
                c('missing',args=b'MISSING',error=205),
                c('close-error',error=202,closeError=202,opens=1),
                c('break',breakAt=0,error=304,opens=1)]
    common[1]['expected']=b'x\n'
    return [c('redirected',b'a\r\nb\x9b',expected=b'a\nb\n'),
            c('page',b'a\nb\nc\nd\n',expected=b'a\nb\nc\nd\n',interactive=1,keys=b' ',opens=1,prompts=1),
            c('quit',b'a\nb\nc\nd\n',expected=b'a\nb\n',interactive=1,keys=b'q',opens=1,prompts=1),
            c('row',b'a\nb\nc\nd\n',expected=b'a\nb\nc\n',interactive=1,keys=b'\nq',opens=1,prompts=2),
            c('wrap',b'1234567890ab\n',expected=b'1234567890ab\n',interactive=1,opens=1),
            c('controls',b'a\t\x01\n',expected=b'a       .\n',interactive=1,opens=1),
            c('interactive-input',dataInteractive=1,error=212),
            c('small-console',interactive=1,width=1,error=115,opens=1)]+common


TEMPLATES = dict(cmp='FROM/A,TO/A',cksum='FILE',hexdump='FILE,OFFSET/K/N,LENGTH/K/N',
                 head='FILE,LINES/K/N',tail='FILE,LINES/K/N',grep='PATTERN/A,FILE,NOCASE/S,INVERT/S,NUMBER/S',
                 list='DIR,NAMES/S',more='FILE',cat='FILE',wc='',hello='')


def vectors(name):
    cases=behavior_vectors(name)
    message=('Arguments: '+(TEMPLATES[name] or '(none)')+'\n').encode()
    for label,args,extra in [
        ('help',b'?',{}),('help-spaces',b' \t?\t ',{}),
        ('help-no-console',b'?',dict(interactive=0,opens=0,error=212,consoleExpected=b'')),
        ('help-write-error',b'?',dict(writeFail=1,error=214,consoleExpected=b'')),
        ('help-close-error',b'?',dict(closeError=202,error=202)),
        ('help-break',b'?',dict(breakAt=0,error=304,consoleExpected=b'')),
    ]:
        case=dict(name=label,payload=b'do not read\n',args=args,expected=b'',
                  interactive=1,opens=1,consoleExpected=message,noReads=True)
        case.update(extra);cases.append(case)
    if name=='grep':
        cases.append(dict(name='quoted-question',payload=b'?\nx\n',args=b'"?"',expected=b'?\n'))
    return cases


def fixture(out,name,cases):
    out.mkdir(parents=True,exist_ok=True)
    for source,target in [('toolbox_state.act','toolboxstate.act'),('toolbox_calls.act','doscalls.act')]:
        (out/target).write_text(read_source(ROOT/'tests/programs'/source))
    (out/'dosclient.act').write_text('''MODULE DOSCLIENT
USE TOOLBOXSTATE AS T
PUBLIC LONGINT FUNC IoErr()
RETURN(T.state.error)
PUBLIC PROC SetError(LONGINT cause)
T.state.error=cause
RETURN
PUBLIC LONGINT FUNC SetIoErr(LONGINT cause)
LET previous=T.state.error
T.state.error=cause
RETURN(previous)
ENDMODULE
''')
    (out/'dosbreak.act').write_text('''MODULE DOSBREAK
USE TOOLBOXSTATE AS T
PUBLIC LONGINT FUNC Pending()
RETURN(LONGINT(T.state.first>=T.scenario.breakAt))
ENDMODULE
''')
    api=read_source(ROOT/'lib/dos/programapi.act').replace('MODULE PROGRAMAPI','MODULE COMMAND').replace('USE EXEC\n','').replace('USE PROCESS\n','USE TOOLBOXSTATE AS T\n')
    api=api.replace('PROCESS.GetArgStr()','CSTRING(@T.scenario.arguments(0))').replace('  EXEC.Yield()','')
    declarations=read_source(ROOT/'lib/dos/command.act').split('PUBLIC EXTERNAL')[0].replace('MODULE COMMAND','')
    api=api.replace('USE DOSFAULT\n','')
    api=api[:api.index('PUBLIC LONGINT FUNC Fault(')]+api[api.index('PUBLIC LONGINT FUNC ReadArgsOrHelp('):]
    marker='; Explicit task-only providers.'
    require(api.count(marker)==1,'Stale command provider declaration marker')
    api=api.replace(marker,declarations+'\n'+marker)
    # The transport fixture exposes the current API; unrelated pane/timer
    # operations reject explicitly rather than importing live drivers.
    for module,signature in [('DOSPANE','PUBLIC BYTE POINTER FUNC Open(CARD rows)'),
                             ('DOSDELAY','PUBLIC LONGINT FUNC Delay(LONGCARD ticks)')]:
        result='NULL' if module=='DOSPANE' else '0'
        (out/(module.lower()+'.act')).write_text(
            f'MODULE {module}\nUSE DOSCLIENT\n{signature}\n\n'
            f'  DOSCLIENT.SetError(209)\n\nRETURN({result})\n\nENDMODULE\n')
    (out/'command.act').write_text(api)
    source=read_source(ROOT/f'examples/commands/{name}.act').replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR').replace('LONGINT FUNC Main()','LONGINT FUNC CommandMain()').replace('ENDMODULE','')
    # Relocate include paths when copying and bind the exact compiler library.
    common=read_source(ROOT/'examples/commands/command-common.inc').replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR')
    (out/'command-common.inc').write_text(common)
    source=source.replace(str(ROOT/'examples/commands/command-common.inc'),str(out/'command-common.inc'))
    source=source.replace('MODULE '+name.upper(),'MODULE '+name.upper()+'\nUSE EXECPOLICY\nUSE TOOLBOXSTATE AS T')
    source+='''
TYPE Observation=[
 LONGINT primary,secondary
 CARD used,consoleUsed,opens,closes,reads,writes
 BYTE ARRAY output(4096)
 BYTE ARRAY console(256)
]
BYTE finished
CARD caseCount,scenarioBytes,rowBytes
PROC Main()
 CARD which,index
 Observation POINTER result
 T.state=T.CaptureState POINTER($c0000)
 scenarioBytes=SIZEOF(T.TestCase)
 rowBytes=SIZEOF(Observation)
 FOR which=0 TO CASE_COUNT-1 DO
  T.scenario=T.TestCase POINTER(ADDRESS($300000)+SIZE(which*SIZEOF(T.TestCase)))
  result=Observation POINTER(ADDRESS($200000)+SIZE(which*SIZEOF(Observation)))
  T.state.error=0 T.state.first=0 T.state.second=0 T.state.reads=0 T.state.writes=0
  T.state.opens=0 T.state.closes=0 T.state.used=0 T.state.consoleUsed=0 T.state.keyAt=0 T.state.entry=0
  result.primary=CommandMain() result.secondary=T.state.error
  result.used=T.state.used result.consoleUsed=T.state.consoleUsed
  result.opens=T.state.opens result.closes=T.state.closes
  result.reads=T.state.reads result.writes=T.state.writes
  FOR index=0 TO 4095 DO result.output(index)=T.state.output(index) OD
  FOR index=0 TO 255 DO result.console(index)=T.state.console(index) OD
  caseCount==+1
 OD
 finished=1
RETURN
ENDMODULE
'''.replace('CASE_COUNT',str(len(cases)))
    path=out/'probe.act';path.write_text(source)
    blob=b''
    for c in cases:
        payload=c['payload'];other=c.get('other',b'')
        blob+=struct.pack('<III12H2B256s32s1100s1100s',c.get('length',len(payload)),c.get('otherLength',len(other)),c.get('breakAt',0xffffffff),
            len(payload),len(other),c.get('chunk',512),c.get('writeChunk',512),
            *(c.get(k,0) for k in ('readFail','writeFail','prefixError','closeError')),
            c.get('width',10),c.get('height',3),c.get('entries',0),c.get('enumerationError',0),
            c.get('interactive',0),c.get('dataInteractive',0),c['args'],c.get('keys',b''),payload,other)
    return path,blob


def run(out,mode,names=NAMES):
    toolchain=compiler(ROOT/'build/actionc')
    records=[]
    for name in names:
        cases=vectors(name);folder=out/name
        path,blob=fixture(folder,name,cases)
        # Fixture-only larger upper-RAM data arena accommodates command BSS and
        # observers together. It changes no bank-zero execution reservation.
        profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=24576 if name=='tail' else 8192
        (folder/'profile.json').write_text(json.dumps(profile))
        p=build(toolchain,path,folder,optimize=mode=='opt',banked=True,console=False,memory_profile=folder/'profile.json',
                image_data=[(0x300000,blob),(0x200000,bytes(STRIDE*len(cases)))])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            runtime,_=execute(b,p,timeout=180,frame_limit=9000)
            require(data(b,p['image'],'finished')==[1],name+' did not finish')
            require(data(b,p['image'],'rowBytes',True)==[STRIDE],name+' result layout')
            actual=data(b,p['image'],'scenarioBytes',True)[0]
            require(actual*len(cases)==len(blob),f'{name} scenario layout {actual} versus {len(blob)//len(cases)}')
            rows=b.memdump(0x200000,STRIDE*len(cases))
            for i,c in enumerate(cases):
                row=rows[i*STRIDE:(i+1)*STRIDE]
                primary,error,used,consoleUsed,opens,closes,reads,writes=struct.unpack('<ii6H',row[:20])
                wanted=(c.get('status',10 if c.get('error') else 0),c.get('error',0))
                require((primary,error)==wanted,f'{name}/{c["name"]}: result {(primary,error)} != {wanted}')
                require(row[20:20+used]==c['expected'],f'{name}/{c["name"]}: output {row[20:20+used]!r} != {c["expected"]!r}')
                require(opens==closes==c.get('opens',0),f'{name}/{c["name"]}: ownership {(opens,closes)}')
                if 'consoleExpected' in c:
                    require(row[4116:4116+consoleUsed]==c['consoleExpected'],name+' diagnostic console')
                if c.get('noReads'):
                    require(reads==0,name+' help consumed Input')
                if c.get('prompts') is not None:
                    require(row[4116:4116+consoleUsed].count(b'--More--')==c['prompts'],name+' prompts')
        records.append(dict(command=name,cases=[c['name'] for c in cases],build=p['build'],runtime=runtime,machine=machine))
        print(name,mode,len(cases),'passed',flush=True)
    return dict(status='pass',tier='development',mode=mode,commands=records,bank_zero_delta=dict(fixed=0,per_task=0),
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [ROOT/'lib/dos/dosargs.act',ROOT/'lib/dos/doscommand.act',ROOT/'lib/dos/dosutility.act',ROOT/'lib/dos/programapi.act',ROOT/'examples/commands/command-common.inc',ROOT/'examples/commands/command-files.inc',Path(__file__),*(ROOT/f'examples/commands/{n}.act' for n in names)]})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--command',choices=NAMES,action='append')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.command or NAMES)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
