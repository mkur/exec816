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
PARAMS='length breakAt readChunk writeChunk readFail prefixError closeError openError seekError mutationError unlockError failTarget failAt writeError writePrefixError zeroTarget oversizedRead same interactive patternBytes'.split()
FIELDS='error position fileCursor fileLength fileHash outputLength outputHash inputLive fileLive consoleLive lockLive opens closes reads fileWrites outputWrites seeks operation mode badOwner consoleUsed'.split()
STATE_BYTES=4*len(FIELDS)+2304
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
RETURN(LONGINT(T.state.position>=T.scenario.breakAt))
ENDMODULE
''')
    api=read_source(ROOT/'lib/dos/programapi.act').replace('MODULE PROGRAMAPI','MODULE COMMAND').replace('USE EXEC\n','').replace('USE PROCESS\n','USE WRITECOMMANDSTATE AS T\n')
    api=api.replace('PROCESS.GetArgStr()','CSTRING(@T.scenario.arguments(0))').replace('  EXEC.Yield()','')
    declarations=read_source(ROOT/'lib/dos/command.act').split('PUBLIC EXTERNAL')[0].replace('MODULE COMMAND','')
    api=api.replace('USE DOSFAULT\n','')
    api=api[:api.index('PUBLIC LONGINT FUNC Fault(')]+api[api.index('PUBLIC LONGINT FUNC ReadArgsOrHelp('):]
    api=api.replace('USE DOSCOMMAND','USE DOSCOMMAND\n'+declarations)
    (out/'command.act').write_text(api)
    includes={n:out/n for n in ('command-files.inc','command-write.inc','command-transfer.inc')}
    for name in includes:
        (out/name).write_text(read_source(ROOT/'examples/commands'/name,includes).replace('USE CSTRING AS STR','USE CSTRING.IMPL AS STR'))
    source=read_source(ROOT/f'examples/commands/{command}.act',includes).replace('LONGINT FUNC Main()','LONGINT FUNC CommandMain()').replace('ENDMODULE','')
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
        blob+=struct.pack('<20I256s768s',*(params.get(k,0) for k in PARAMS),c['args'],c['payload'])
    return path,bytes(blob)


def run(out,mode,names):
    toolchain=compiler(ROOT/'build/actionc');records=[]
    for name in names:
        cases=vectors(name);folder=out/name;path,blob=fixture(folder,name,cases)
        p=build(toolchain,path,folder,optimize=mode=='opt',banked=True,console=False,
                image_data=[(0xc0000,bytes(STATE_BYTES)),(0x300000,blob),(0x200000,bytes(ROW_BYTES*len(cases)))])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            runtime,_=execute(b,p,timeout=240,frame_limit=12000)
            require(data(b,p['image'],'finished')==[1],name+' did not finish')
            require(data(b,p['image'],'rowBytes',True)==[ROW_BYTES],name+' result layout')
            require(data(b,p['image'],'scenarioBytes',True)==[1104],name+' scenario layout')
            rows=b.memdump(0x200000,ROW_BYTES*len(cases))
            for index,c in enumerate(cases):
                row=rows[index*ROW_BYTES:(index+1)*ROW_BYTES]
                primary=struct.unpack('<i',row[:4])[0];state=dict(zip(FIELDS,struct.unpack('<21I',row[4:88])))
                wanted=(10 if c.get('error') else 0,c.get('error',0))
                require((primary,state['error'])==wanted,f'{name}/{c["name"]}: result {(primary,state["error"])} != {wanted}')
                require(state['badOwner']==0 and all(state[f]==0 for f in ('inputLive','fileLive','consoleLive','lockLive')),f'{name}/{c["name"]}: retained/borrowed ownership')
                require(state['opens']==state['closes']==c['opens'],f'{name}/{c["name"]}: closes {state}')
                require(state['operation']==c['operation'],name+' unexpected namespace mutation')
                for key,at in [('file',88),('output',1112)]:
                    expected=c[key]
                    require(state[key+'Length']==len(expected) and state[key+'Hash']==rolling(expected),f'{name}/{c["name"]}: {key} length/hash {state}')
                    require(row[at:at+min(1024,len(expected))]==expected[:1024],f'{name}/{c["name"]}: {key} prefix')
                require(row[2136:2136+state['consoleUsed']]==c.get('console',b''),name+' help console')
                if c.get('noReads'):require(state['reads']==0,name+' help read Input')
                require(state['seeks']==c.get('seeks',0),name+' unexpected seek')
                if 'mode' in c:require(state['mode']==c['mode'],name+' wrong open mode')
        records.append(dict(command=name,cases=[c['name'] for c in cases],build=p['build'],runtime=runtime,machine=machine))
        print(name,mode,len(cases),'passed',flush=True)
    return dict(status='pass',tier='development',mode=mode,commands=records,bank_zero_delta=dict(fixed=0,per_task=0),
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [Path(__file__),ROOT/'tests/programs/write_commands_calls.act',ROOT/'tests/programs/write_commands_state.act',
                    *(ROOT/'examples/commands'/n for n in ('command-files.inc','command-write.inc','command-transfer.inc')),
                    *(ROOT/f'examples/commands/{n}.act' for n in names)]})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--command',choices=TEMPLATES,action='append')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.case,args.command or list(TEMPLATES))
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
