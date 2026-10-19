#!/usr/bin/env python3
"""TAB replacement and cursor checks on the packaged bitmap console."""
import argparse,json,zipfile
from pathlib import Path
from types import SimpleNamespace
from native_program import require,sha256
from test_demo import run


def check(bundle):
    distribution=bundle/'distribution'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(distribution)
    def exercise(c):
        baseline=c.ledger()
        for text,wanted,left in [('UNM','UNMOUNT ',0),
                                 ('TYPE SYS:READM tail','TYPE SYS:README.TXT tail',5),
                                 ('TYPE '+' '*30+'SYS:READM','TYPE '+' '*30+'SYS:README.TXT ',0)]:
            for char in text:c.press(char)
            for _ in range(left):c.press('\x02')
            generation=c.number(c.saved['scope']+14)
            c.press('\t');c.ready();c.cells('bitmap-completion')
            session=c.number(c.number(c.saved['shell'],3)+16,3)
            length=c.number(session+2,2)
            require(c.far(session+16,length)==wanted.encode(),'Wrong bitmap completion')
            require(c.number(session+402,2)==len(wanted)-left,'Wrong completion cursor')
            require(c.number(c.saved['scope']+14)==generation,'TAB submitted bitmap command')
            require(c.ledger()==baseline,'Bitmap completion retained ownership')
            c.press('\x15');c.ready()
        c.save_screen(c.p['output']/'boot-smoke.png')
        for char in 'EXIT':c.press(char)
        c.b._cmd_ok('KEY RETURN down');c.b.bp_clear_all()
    result=run(bundle,boot_smoke=True,distribution_root=distribution/'exec816-demo',
               integration=SimpleNamespace(exercise=exercise))
    result.update(scope='Extracted OF816 bitmap shell: TAB, following text, mid-line caret, horizontal viewport, independent pixels and EXIT.',
                  package_sha256=sha256(bundle/'exec816-demo.zip'))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();bundle=args.bundle.resolve();result=check(bundle)
    (bundle/'completion-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap completion passed',flush=True)
