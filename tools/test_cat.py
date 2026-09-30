#!/usr/bin/env python3
"""Focused emitted-code CAT checks using bounded, byte-exact stream fixtures."""
import argparse
import json
import struct
from pathlib import Path
from library_paths import read_source

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def cases():
    return [
        dict(name='empty', length=0),
        dict(name='binary', length=1025),
        dict(name='short-reads-writes', length=1031, chunk=19, writeChunk=7),
        dict(name='quoted-path', length=513, argument=b'"A B"', path=b'A B'),
        dict(name='escaped-path', length=7, argument=b'"A**B"', path=b'A*B'),
        dict(name='too-many-args', length=0, argument=b'one two', cause=118, copied=0),
        dict(name='unterminated', length=0, argument=b'"bad', cause=119, copied=0),
        dict(name='empty-filename', length=0, argument=b'""', cause=210),
        dict(name='tab-path', length=5, argument=b'\t"A B"\t', path=b'A B'),
        dict(name='open-error', length=0, argument=b'FILE', path=b'FILE', openError=205, cause=205),
        dict(name='close-error', length=20, argument=b'FILE', path=b'FILE', closeError=202, cause=202),
        dict(name='read-error', length=1025, readFail=2, cause=226, copied=512),
        dict(name='write-error', length=1025, writeFail=2, cause=214, copied=512),
        dict(name='break-before-open', length=512, argument=b'FILE', breakAt=0, cause=304, copied=0),
        dict(name='break-after-read', length=1025, breakAt=513, cause=304, copied=512),
        dict(name='zero-write', length=512, zeroWrite=1, cause=206, copied=0),
        dict(name='causal-error', length=1025, argument=b'FILE', path=b'FILE', readFail=2,
             closeError=202, cause=226, copied=512),
    ]


def command_source(text):
    text=text.replace('\r\n','\n')
    require(text.count('LONGINT FUNC Main()')==1,'Missing command entry')
    return text.replace('LONGINT FUNC Main()','LONGINT FUNC CopyInput()')


def run(out, mode, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    (out/'command.act').write_text(read_source(ROOT/'tests/programs/cat_stream.act'))
    vectors = cases()
    source = command_source((ROOT/'examples/commands/cat.act').read_text())
    source = source.replace('USE COMMAND', 'USE COMMAND\nUSE EXECPOLICY').replace('ENDMODULE', '')
    source = source.replace('USE CSTRING AS STR', 'USE CSTRING.IMPL AS STR', 1)
    source += '''
TYPE Observation=[LONGINT primary,secondary LONGCARD written CARD opens,closes,mismatch BYTE ARRAY name(32)]
Observation ARRAY observations(CASE_COUNT)
CARD rowBytes,scenarioBytes
BYTE finished
PROC Main()
  CARD which,index
  rowBytes=SIZEOF(Observation) scenarioBytes=SIZEOF(COMMAND.Scenario)
  FOR which=0 TO CASE_COUNT-1 DO
    COMMAND.current=COMMAND.Scenario POINTER(ADDRESS($e0000)+SIZE(which*SIZEOF(COMMAND.Scenario)))
    COMMAND.Reset() COMMAND.primary=CopyInput() COMMAND.secondary=COMMAND.IoErr()
    observations(which).primary=COMMAND.primary observations(which).secondary=COMMAND.secondary
    observations(which).written=COMMAND.written observations(which).opens=COMMAND.opens
    observations(which).closes=COMMAND.closes observations(which).mismatch=COMMAND.mismatch
    FOR index=0 TO 31 DO observations(which).name(index)=COMMAND.openedName(index) OD
  OD
  finished=1
RETURN
ENDMODULE
'''
    source=source.replace('CASE_COUNT',str(len(vectors)))
    fixture = out/'cat_probe.act'
    fixture.write_text(source)
    blob = b''.join(struct.pack('<II8H32s', c['length'], c.get('breakAt', 0xffffffff),
        c.get('chunk',512), c.get('writeChunk',512), len(c.get('argument',b'')),
        *(c.get(k,0) for k in ('readFail','writeFail','openError','closeError','zeroWrite')),
        c.get('argument',b'')) for c in vectors)
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc'),fixture,out,
        optimize=mode=='opt',banked=True,console=False,image_data=[(0xe0000,blob)])
    require(p['build']['source_sha256']==sha256(fixture), 'Stale CAT fixture')
    require(any(s['address']==0xe0000 and bytes(s['bytes'])==blob for s in p['image']['segments']), 'Stale vectors')
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==PIN['emulator']['sha256'] and sha256(rom)==PIN['rom']['sha256'], 'Unpinned machine')
    with emulator(binary.parent,rom,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,rom,PIN)
        runtime,_=execute(b,p,timeout=90,frame_limit=4500)
        require(data(b,p['image'],'finished')==[1], 'Missing CAT completion')
        require(data(b,p['image'],'scenarioBytes',True)==[56], 'Scenario layout')
        stride=int.from_bytes(bytes(data(b,p['image'],'rowBytes')),'little')
        rows=bytes(data(b,p['image'],'observations'))
        for i,c in enumerate(vectors):
            row=rows[i*stride:(i+1)*stride]
            primary,cause,written,opens,closes,mismatch=struct.unpack('<iiIHHH',row[:18])
            expected=c.get('cause',0)
            require((primary,cause)==(10 if expected else 0,expected), 'CAT result: '+c['name'])
            require(written==c.get('copied',c['length']) and mismatch==0, 'CAT bytes: '+c['name'])
            named=bool(c.get('path'))
            require(opens==int(named) and closes==int(named and not c.get('openError')), 'CAT ownership: '+c['name'])
            require(row[18:50].split(b'\0',1)[0]==c.get('path',b''), 'CAT filename: '+c['name'])
    return dict(status='pass',tier='development',mode=mode,cases=[c['name'] for c in vectors],build=p['build'],
                runtime=runtime,machine=machine,pin=PIN,bank_zero_delta=dict(fixed=0,per_task=0),
                source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in
                (ROOT/'examples/commands/cat.act',ROOT/'tests/programs/cat_stream.act',ROOT/'lib/dos/dosargs.act',Path(__file__))})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('CAT checks passed:',args.case,len(result['cases']))
