#!/usr/bin/env python3
"""Actual writable command bodies, resident parser and WriteAll on controlled I/O."""
import argparse
import json
import struct
from pathlib import Path
from library_paths import read_source
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256
from os_boundary import emulator
from test_cooperative import data

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
TEMPLATES={'copy':'FROM/A,TO/A,APPEND/S','tee':'FILE/A,APPEND/S',
           'delete':'FILE/M/A','rename':'FROM/A,TO/A','makedir':'NAME/A'}
PARAMS='length breakAt readChunk writeChunk readFail prefixError closeError openError seekError mutationError unlockError failTarget failAt writeError writePrefixError zeroTarget oversizedRead same interactive patternBytes destinationKind lockError examineError enumerate enumCount enumErrorAt enumDirMask enumBreakAt'.split()
FIELDS='error position fileCursor fileLength fileHash outputLength outputHash inputLive fileLive consoleLive lockLive opens closes reads fileWrites outputWrites seeks operation mode badOwner consoleUsed lockCalls examines targetUsed enumCalls enumCursor enumLock'.split()
SCENARIO_BYTES=4*len(PARAMS)+1024
STATE_BYTES=4*len(FIELDS)+2560
ROW_BYTES=4+STATE_BYTES


def rolling(value):
    result=0
    for byte in value:result=(result*33+byte)&0xffffffff
    return result


def vectors(command):
    args=b'A B' if command in ('copy','rename') else b'B'
    def c(name, payload=b'', **changes):
        transfer=command in ('copy','tee')
        item=dict(name=name,args=args,payload=payload,file=payload if transfer else b'old',
                  output=payload if command=='tee' else b'',opens=2 if command=='copy' else 1 if command in ('tee','makedir') else 0,
                  operation={'delete':1,'rename':2,'makedir':3}.get(command,0))
        item.update(changes)
        return item
    common=[c('empty-name',args=b'A ""' if command in ('copy','rename') else b'""',error=210,opens=0,operation=0,file=b'old'),
            c('missing-argument',args=b'A' if command in ('copy','rename') else b'',error=116,opens=0,operation=0,file=b'old'),
            c('break-before',breakAt=0,error=304,opens=0,operation=0,file=b'old')]
    if command in ('copy','tee'):
        payload=bytes(range(256))*3
        result=[c('empty'),c('binary',payload),c('short',payload,readChunk=73,writeChunk=7),
                c('wide',b'x',length=65537,file=b'x'*65537,output=b'x'*65537 if command=='tee' else b''),
                c('append',b'\x00\x9b\xff',args=args+b' APPEND',file=b'old\x00\x9b\xff',seeks=1,mode=1004),
                c('output-open-error',b'x',openError=214,error=214,file=b'old',output=b'',opens=1 if command=='copy' else 0),
                c('same-object',b'x',same=1,error=202,file=b'old',output=b'',opens=1 if command=='copy' else 0),
                c('seek-error',b'x',args=args+b' APPEND',seekError=219,error=219,seeks=1,mode=1004,file=b'old',output=b''),
                c('seek-before-close-error',b'x',args=args+b' APPEND',seekError=219,closeError=202,error=219,seeks=1,mode=1004,file=b'old',output=b''),
                c('read-error',b'x',readFail=1,error=226,file=b'',output=b''),
                c('prefix-error',b'abc',prefixError=226,error=226),
                c('prefix-before-write-error',b'abc',prefixError=226,failTarget=2,failAt=1,writeError=214,error=226,file=b'',output=b''),
                c('file-error',b'abc',failTarget=2,failAt=1,writeError=214,error=214,file=b'',output=b''),
                c('file-prefix-error',b'abc',failTarget=2,writeChunk=1,writePrefixError=206,error=206,file=b'a',output=b''),
                c('zero-write',b'abc',zeroTarget=2,error=206,file=b'',output=b''),
                c('write-before-close-error',b'abc',failTarget=2,failAt=1,writeError=214,closeError=202,error=214,file=b'',output=b''),
                c('close-error',b'abc',closeError=202,error=202),
                c('oversized-read',b'abc',oversizedRead=1,error=206,file=b'',output=b''),
                c('break-between',b'x'*768,breakAt=600,error=304,file=b'x'*512,output=b'x'*512 if command=='tee' else b'')]
        if command=='copy':result.append(c('missing-source',b'x',args=b'MISSING B',error=205,file=b'old',output=b'',opens=0))
        else:result.extend([c('mirror-error',b'abc',failTarget=3,failAt=1,writeError=310,error=310,output=b''),
                            c('mirror-prefix-error',b'abc',failTarget=3,writeChunk=1,writePrefixError=310,error=310,output=b'a'),
                            c('prefix-before-mirror-error',b'abc',prefixError=226,failTarget=3,failAt=1,writeError=310,error=226,output=b'')])
        if command=='copy':
            result.extend([
                c('existing-file',b'abc',destinationKind=1,opens=2,target=b'B'),
                c('wrong-type-file',b'abc',destinationKind=1,openError=212,
                  opens=2,error=212,file=b'old',target=b'B'),
                c('directory-root',b'abc',args=b'SYS:SUB/ONE.TXT RAM:',
                  destinationKind=2,opens=3,target=b'RAM:ONE.TXT'),
                c('directory-named',b'abc',args=b'SYS:ONE.TXT RAM:SUB',
                  destinationKind=2,opens=3,target=b'RAM:SUB/ONE.TXT'),
                c('directory-relative',b'abc',args=b'SUB/ONE.TXT DEST',
                  destinationKind=2,opens=3,target=b'DEST/ONE.TXT'),
                c('directory-current',b'abc',args=b'SYS:ONE.TXT .',
                  destinationKind=2,opens=3,target=b'ONE.TXT'),
                c('directory-append',b'abc',args=b'SYS:ONE.TXT RAM: APPEND',
                  destinationKind=2,opens=3,target=b'RAM:ONE.TXT',
                  file=b'oldabc',seeks=1,mode=1004),
                c('directory-same-object',b'abc',args=b'SYS:ONE.TXT SYS:',
                  destinationKind=2,same=1,opens=2,error=202,file=b'old',
                  target=b'SYS:ONE.TXT'),
                c('stream-target',b'abc',args=b'A NIL:',destinationKind=3,
                  target=b'NIL:'),
                c('stream-source-no-leaf',b'',args=b'NIL: RAM:',
                  destinationKind=2,opens=2,error=210,file=b'old',target=b'RAM:'),
                c('destination-lock-error',b'abc',destinationKind=2,
                  lockError=213,error=213,opens=1,file=b'old',target=b'B'),
                c('destination-examine-error',b'abc',destinationKind=2,
                  examineError=226,error=226,opens=2,file=b'old',target=b'B'),
                c('destination-unlock-error',b'abc',destinationKind=2,
                  unlockError=202,error=202,opens=2,file=b'old',target=b'B'),
                c('examine-before-unlock-error',b'abc',destinationKind=2,
                  examineError=226,unlockError=202,error=226,opens=2,
                  file=b'old',target=b'B'),
                c('probe-before-source-close-error',b'abc',destinationKind=2,
                  lockError=213,closeError=202,error=213,opens=1,file=b'old',target=b'B')])
            pattern=bytes(range(256))
            for length in (1,511,512,513,16383,16384,16385,49159):
                expected=(pattern*((length+255)//256))[:length]
                result.append(c(f'capacity-{length}',pattern,length=length,
                                readChunk=16384,writeChunk=16384,file=expected,
                                reads=(length+16383)//16384+1))
    else:
        result=[c('success'),c('mutation-error',mutationError=214,error=214,opens=0)]
        if command=='makedir':result.append(c('unlock-error',unlockError=202,error=202))
        if command=='delete':
            result.extend([c('two-names',args=b'A B',operation=2,mode=65*33+66),
                           c('empty-second',args=b'A ""',error=210,operation=0),
                           c('missing-second',args=b'A MISSING',error=205,operation=2,mode=65*33+77),
                           c('second-error',args=b'A B',failAt=2,mutationError=214,error=214,
                             operation=2,mode=65*33+66),
                           c('break-between',args=b'A B',breakAt=1,error=304,operation=1,mode=65)])
    message=('Arguments: '+TEMPLATES[command]+'\n').encode()
    common.extend([c('help',args=b'?',interactive=1,opens=1,operation=0,file=b'old',console=message,noReads=True),
                   c('help-no-console',args=b'?',interactive=0,error=212,opens=0,operation=0,file=b'old',noReads=True)])
    if command in ('copy', 'delete'):
        def glob(name, **changes):
            item = c(name, b'abc' if command == 'copy' else b'',
                     args=b'S:a?.t*t B' if command == 'copy' else b'S:a?.t*t',
                     enumerate=1, enumCount=3, destinationKind=2,
                     opens=8 if command == 'copy' else 1,
                     operation=0 if command == 'copy' else 3,
                     lockCalls=2 if command == 'copy' else 1,
                     examines=2 if command == 'copy' else 1, enumCalls=4)
            item.update(changes)
            return item
        def rejected(name, error, **changes):
            item = dict(error=error, file=b'old', opens=1, operation=0,
                        lockCalls=1, examines=1)
            item.update(changes)
            return glob(name, **item)
        result.extend([
            glob('glob-three', target=b'B/A2.TXT' if command == 'copy' else b''),
            glob('glob-eight', enumCount=8, enumCalls=9,
                 opens=18 if command == 'copy' else 1,
                 operation=0 if command == 'copy' else 8),
            rejected('glob-nine', 118, enumCount=9, enumCalls=9),
            rejected('glob-empty', 205, enumCount=0, enumCalls=1),
            rejected('glob-no-match', 205, enumCalls=4,
                     args=b'S:*.BIN B' if command == 'copy' else b'S:*.BIN'),
            rejected('glob-enumeration-error', 226, enumErrorAt=3, enumCalls=3),
            rejected('glob-break', 304, enumBreakAt=2, enumCalls=2),
            rejected('glob-unlock-error', 202, unlockError=202, enumCalls=4),
            rejected('glob-error-before-unlock', 226, enumErrorAt=3,
                     unlockError=202, enumCalls=3),
            rejected('glob-source-too-long', 120, enumCalls=1,
                     args=b'S:'+b'X'*248+b'/*'+(b' B' if command == 'copy' else b'')),
            c('glob-parent-pattern', args=b'S:*/A B' if command == 'copy' else b'S:*/A',
              error=311, file=b'old', opens=0, operation=0,
              lockCalls=0, examines=0, enumCalls=0),
        ])
        if command == 'copy':
            result.extend([
                glob('glob-skips-directories', enumDirMask=2, opens=6),
                glob('glob-append', args=b'S:*.TXT B APPEND', file=b'oldabc',
                     seeks=3, mode=1004),
                rejected('glob-regular-target', 212, destinationKind=1,
                         lockCalls=2, examines=2, opens=2, enumCalls=4),
                c('glob-destination-pattern', args=b'A B*', error=311,
                  file=b'old', opens=0, operation=0, lockCalls=0, examines=0),
                rejected('glob-destination-too-long', 120,
                         args=b'S:* '+b'B'*251, opens=2,
                         lockCalls=2, examines=2, enumCalls=4),
            ])
        else:
            result.extend([
                glob('glob-includes-directories', enumDirMask=2),
                rejected('glob-later-no-match', 205,
                         args=b'EXACT S:*.TXT S:*.BIN', opens=2,
                         lockCalls=2, examines=2, enumCalls=8),
                rejected('glob-combined-overflow', 118,
                         args=b'EXACT S:*.TXT', enumCount=8, enumCalls=8),
                glob('glob-delete-second-error', mutationError=216, failAt=2,
                     error=216, operation=2),
            ])
    return result+common


def fixture(out,command,cases):
    out.mkdir(parents=True,exist_ok=True)
    for name,target in [('write_commands_state.act','writecommandstate.act'),('write_commands_calls.act','doscalls.act')]:
        (out/target).write_text(read_source(ROOT/'tests/programs'/name))
    (out/'dosclient.act').write_text('''MODULE DOSCLIENT
USE WRITECOMMANDSTATE AS T
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
USE WRITECOMMANDSTATE AS T
PUBLIC LONGINT FUNC Pending()
RETURN(LONGINT(T.state.position>=T.scenario.breakAt OR
    (T.scenario.enumBreakAt<>0 AND T.state.enumCalls>=T.scenario.enumBreakAt)))
ENDMODULE
''')
    api=read_source(ROOT/'lib/dos/programapi.act').replace('MODULE PROGRAMAPI','MODULE COMMAND').replace('USE EXEC\n','').replace('USE PROCESS\n','USE WRITECOMMANDSTATE AS T\n')
    api=api.replace('PROCESS.GetArgStr()','CSTRING(@T.scenario.arguments(0))').replace('  EXEC.Yield()','')
    declarations=read_source(ROOT/'lib/dos/command.act').split('PUBLIC EXTERNAL')[0].replace('MODULE COMMAND','')
    api=api.replace('USE DOSFAULT\n','').replace('USE DOSPANE\n','').replace('USE DOSDELAY\n','')
    api=api[:api.index('PUBLIC LONGINT FUNC WriteAt(')]+api[api.index('PUBLIC LONGINT FUNC Seek('):]
    api=api[:api.index('PUBLIC LONGINT FUNC Delay(')]+'ENDMODULE\n'
    api=api[:api.index('PUBLIC LONGINT FUNC Fault(')]+api[api.index('PUBLIC LONGINT FUNC ReadArgsOrHelp('):]
    api=api.replace('USE DOSCOMMAND\n','USE DOSCOMMAND\n'+declarations)
    (out/'command.act').write_text(api)
    includes={n:out/n for n in ('command-files.inc','command-write.inc','command-transfer.inc',
                              'command-pattern.inc','command-selection.inc')}
    for name in includes:
        (out/name).write_text(read_source(ROOT/'examples/commands'/name,includes).replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR'))
    source=read_source(ROOT/f'examples/commands/{command}.act',includes).replace('LONGINT FUNC Main()','LONGINT FUNC CommandMain()').replace('ENDMODULE','').replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR')
    if command=='copy':
        # The resident probe has a 2 KiB data budget. Use a guarded diagnostic
        # extent crossing a bank; the loadable command's ordinary BSS is
        # checked separately through its object profile and shell loading.
        source=source.replace('BYTE ARRAY transferBuffer(TRANSFER_BYTES)',
                              'BYTE POINTER transferBuffer')
        source=source.replace('  LET parsed=',
                              '  transferBuffer=BYTE POINTER($afff0)\n  LET parsed=',1)
    source=source.replace('MODULE '+command.upper(),'MODULE '+command.upper()+'\nUSE EXECPOLICY\nUSE WRITECOMMANDSTATE AS T')
    source+='''
TYPE Observation=[LONGINT primary T.CaptureState capture]
BYTE finished
CARD caseCount,scenarioBytes,rowBytes
PROC Main()
  CARD which,index
  BYTE POINTER sourceBytes,targetBytes
  Observation POINTER observed

  T.state=T.CaptureState POINTER($c0000)
  scenarioBytes=SIZEOF(T.TestCase)
  rowBytes=SIZEOF(Observation)
  FOR which=0 TO CASE_COUNT-1 DO
    T.scenario=T.TestCase POINTER(ADDRESS($300000)+SIZE(which)*SIZE(SIZEOF(T.TestCase)))
    observed=Observation POINTER(ADDRESS($200000)+SIZE(which)*SIZE(SIZEOF(Observation)))
RESET
    T.state.fileLength=3
    T.state.fileHash=124543
    T.state.file(0)='o
    T.state.file(1)='l
    T.state.file(2)='d
    observed.primary=CommandMain()
    sourceBytes=BYTE POINTER(T.state)
    targetBytes=BYTE POINTER(@observed.capture)
    FOR index=0 TO CARD(SIZEOF(T.CaptureState))-1 DO
      targetBytes(index)=sourceBytes(index)
    OD
    caseCount==+1
  OD
  finished=1
RETURN
ENDMODULE
'''.replace('CASE_COUNT',str(len(cases))).replace('RESET','\n'.join('    T.state.'+f+'=0' for f in FIELDS))
    path=out/'probe.act';path.write_text(source)
    blob=bytearray()
    for c in cases:
        params=dict(length=len(c['payload']),breakAt=0xffffffff,readChunk=512,writeChunk=512,patternBytes=len(c['payload']))
        params.update({k:v for k,v in c.items() if k in PARAMS})
        require(len(c['payload'])<=768,'Fixture pattern too large')
        blob+=struct.pack('<'+str(len(PARAMS))+'I256s768s',
                          *(params.get(k,0) for k in PARAMS),c['args'],c['payload'])
    return path,bytes(blob)


def run(out,mode,names,selected=None,compiler_bin=None):
    toolchain=compiler(ROOT/'build/actionc');records=[]
    if compiler_bin:
        toolchain['binary']=Path(compiler_bin).resolve()
        toolchain['binary_sha256']=sha256(toolchain['binary'])
    for name in names:
        cases=[c for c in vectors(name) if selected is None or c['name'] in selected]
        require(cases,'No selected command cases')
        folder=out/name;path,blob=fixture(folder,name,cases)
        p=build(toolchain,path,folder,optimize=mode=='opt',banked=True,console=False,
                image_data=[(0xc0000,bytes(STATE_BYTES)),(0x300000,blob),
                            (0x200000,bytes(ROW_BYTES*len(cases))),
                            (0xaffd0,bytes([0xa5])*(16384+64))])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            runtime,_=execute(b,p,timeout=240,frame_limit=12000)
            require(data(b,p['image'],'finished')==[1],name+' did not finish')
            require(data(b,p['image'],'rowBytes',True)==[ROW_BYTES],name+' result layout')
            require(data(b,p['image'],'scenarioBytes',True)==[SCENARIO_BYTES],name+' scenario layout')
            rows=b.memdump(0x200000,ROW_BYTES*len(cases))
            for index,c in enumerate(cases):
                row=rows[index*ROW_BYTES:(index+1)*ROW_BYTES]
                field_end=4+4*len(FIELDS)
                primary=struct.unpack('<i',row[:4])[0];state=dict(zip(FIELDS,
                    struct.unpack('<'+str(len(FIELDS))+'I',row[4:field_end])))
                wanted=(10 if c.get('error') else 0,c.get('error',0))
                require((primary,state['error'])==wanted,f'{name}/{c["name"]}: result {(primary,state["error"])} != {wanted}')
                require(state['badOwner']==0 and all(state[f]==0 for f in ('inputLive','fileLive','consoleLive','lockLive')),f'{name}/{c["name"]}: retained/borrowed ownership')
                require(state['opens']==state['closes']==c['opens'],f'{name}/{c["name"]}: closes {state}')
                require(state['operation']==c['operation'],name+' unexpected namespace mutation')
                for key,at in [('file',field_end),('output',field_end+1024)]:
                    expected=c[key]
                    require(state[key+'Length']==len(expected) and state[key+'Hash']==rolling(expected),f'{name}/{c["name"]}: {key} length/hash {state}')
                    require(row[at:at+min(1024,len(expected))]==expected[:1024],f'{name}/{c["name"]}: {key} prefix')
                console_at=field_end+2048
                require(row[console_at:console_at+state['consoleUsed']]==c.get('console',b''),name+' help console')
                if 'target' in c:
                    target_at=console_at+256
                    require(state['targetUsed']==len(c['target']) and
                            row[target_at:target_at+state['targetUsed']]==c['target'],
                            f'{name}/{c["name"]}: wrong destination')
                if name=='copy':
                    probed=c.get('destinationKind')==2 or c.get('openError')==212
                    examined=bool(probed and c.get('destinationKind') in (1,2)
                                  and not c.get('lockError'))
                    require((state['lockCalls'],state['examines'])==
                            (c.get('lockCalls', int(probed)),c.get('examines', int(examined))),
                            f'{name}/{c["name"]}: unexpected directory inspection')
                if 'enumCalls' in c:
                    require(state['enumCalls']==c['enumCalls'],
                            f'{name}/{c["name"]}: unexpected enumeration count')
                if c.get('noReads'):require(state['reads']==0,name+' help read Input')
                if 'reads' in c:require(state['reads']==c['reads'],name+' chunk count')
                require(state['seeks']==c.get('seeks',0),name+' unexpected seek')
                if 'mode' in c:require(state['mode']==c['mode'],name+' wrong open mode')
            if name=='copy':
                for at in (0xaffd0,0xafff0+16384):
                    require(all(b.eval_expr(f'db(${at+i:x})')==0xa5 for i in range(32)),
                            'COPY diagnostic buffer guard changed')
        records.append(dict(command=name,cases=[c['name'] for c in cases],build=p['build'],runtime=runtime,machine=machine))
        print(name,mode,len(cases),'passed',flush=True)
    return dict(status='pass',tier='development',mode=mode,commands=records,bank_zero_delta=dict(fixed=0,per_task=0),
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [Path(__file__),ROOT/'tests/programs/write_commands_calls.act',ROOT/'tests/programs/write_commands_state.act',
                    *(ROOT/'examples/commands'/n for n in ('command-files.inc','command-write.inc','command-transfer.inc','command-pattern.inc','command-selection.inc')),
                    *(ROOT/f'examples/commands/{n}.act' for n in names)]})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--command',choices=TEMPLATES,action='append')
    parser.add_argument('--suite',help='Comma-separated focused case names')
    parser.add_argument('--compiler-bin',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.case,args.command or list(TEMPLATES),
                   args.suite.split(',') if args.suite else None,args.compiler_bin)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
