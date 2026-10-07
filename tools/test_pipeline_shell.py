#!/usr/bin/env python3
"""D5: physical two-stage pipelines, redirection, loading failure and BREAK."""
import argparse
import json
import shutil
from pathlib import Path
from build_command import compile_command
from make_shell_disk import make
from native_program import ROOT, compiler, require, sha256
from test_o65_shell import Commands
from test_shell_core import run, draw


class Pipelines(Commands):
    def prepare(self, toolchain, out, mode, size):
        require(size == 128, 'Pipeline smoke geometry')
        source=out/'files';source.mkdir(exist_ok=True)
        self.commands={}
        for name in ('HELLO','CAT','WC'):
            self.commands[name]=compile_command(toolchain,ROOT/f'examples/commands/{name.lower()}.act',source/name,mode=='opt')
            (source/(name+'.options.json')).rename(out/(name+'.options.json'))
            (source/(name+'.profile.json')).rename(out/(name+'.profile.json'))
        for name in ('STORY.TXT','LONG.TXT'):
            shutil.copyfile(ROOT/'examples/demo-disk'/name,source/name)
        self.files=make(out/'volume.atr',source,binary_names=set(self.commands))

    def exercise(self,c):
        c.command('HELLO|WC',b'1 3 17\n')
        story=self.files['STORY.TXT']
        lines=story.count(b'\n')
        counts=f'{lines} {len(story.split())} {len(story)}\n'.encode('ascii')
        c.command('CAT "STORY.TXT" | WC',counts)
        c.command('CAT <STORY.TXT | WC >NIL:')
        c.command('CAT <NIL:|WC',b'0 0 0\n')
        for command in ('|WC','HELLO|','HELLO|WC|CAT','HELP|WC','HELLO|TYPE','HELLO >NIL:|WC','CAT|WC <NIL:'):
            c.command(command,error=115)
        c.command('HELLO|MISSING',error=205)
        c.command('CAT MISSING|WC',b'0 0 0\n',error=205)
        c.check_screen('pipelines')
        c.append('CAT LONG.TXT|WC')
        previous=c.b.peek16(c.at('commandCount'))
        c.press('\n')
        # Two child scopes are linked through the parent scope retained in the
        # first member's Process row. Require an active file Read, not loading.
        base=c.p['build']['memory']['process_storage']['BASE']
        c.rendezvous(f'dw(${base+4*128+121:x})!=0')
        group=int.from_bytes(c.far(base+4*128+121,3),'little')
        c.rendezvous(f'(dw(${group+48:x})!=0)&(dw(${group+51:x})!=0)')
        scopes=[int.from_bytes(c.far(group+offset,3),'little') for offset in (48,51)]
        active=lambda scope:f'(db(${scope+21:x})=3)&(dw(dw(${scope+27:x})+db(${scope+29:x})*65536+22)=82)'
        c.rendezvous('|'.join(f'({active(scope)})' for scope in scopes))
        c.press('\x03')
        c.rendezvous(f'dw(${c.at("commandCount"):x})={previous+1}')
        c.ready();c.expected.extend(b'\n');c.line.clear();c.expected.extend(draw(c.line))
        result=c.far(c.state['shell']+32,8)
        require(tuple(int.from_bytes(result[i:i+4],'little',signed=True) for i in (0,4))==(10,304),'Pipeline BREAK result')
        c.command('HELLO|WC',b'1 3 17\n')
        c.check_screen('pipeline-break-recovery')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args();out=args.output.resolve();scenario=Pipelines()
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    frozen={name:sha256(out/name) for name in ('shell-observed.inc','doscooked.act','programapi.act','shelleditprobe.act')} if args.reuse else {}
    result=run(compiler(ROOT/'build/actionc'),out,args.case,external=scenario,reuse=args.reuse,
               pin=pin,bridge_build=ROOT/'build/shell-paced-bridge')
    require(all(sha256(out/name)==digest for name,digest in frozen.items()),'Changed shell observers')
    result.update(commands=scenario.commands,runner_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pipeline physical shell passed:',args.case)
