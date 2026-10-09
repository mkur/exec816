#!/usr/bin/env python3
"""Focused exact-package viewer resize/scrollbar diagnostic."""
import argparse,json,zipfile
from native_program import require
from pathlib import Path
from test_standard_dialog_demo import DialogDemo
from test_demo import run
from gem_applications import symbols
from text_model import FIELDS as F,LOAD_PHASE

class Gadgets(DialogDemo):
    extensions_only=True
    capacity_app='TEXT'
    def selectors(self,s,shared,menus,counter,launch,accept,phase,move,edge,click,key,collected,owners,memory,baseline):
        menus.select('Shell');old=s.begin('RUN C:TEXT.APP SYS:STORY.TXT');s.ready(old);s.result()
        a=symbols(s.b,s.p,s.p['output']/'bitmap-console','text',s.number(s.at('job'),4))['GEMText']
        def settled():
            s.rendezvous('(dw($%x)=1)&(dw($%x)=0)&(dw($%x)=0)'%(a+F['ready'],a+F['dirty'],a+F['load']+LOAD_PHASE))
            s.frames(70)
        settled();menus.select('STORY.TXT');key('SPACE');key('SPACE');settled()
        x,y,w,h=[s.number(a+F['work']+i*2,2) for i in range(4)]
        click(x+w+8,y+8);settled()
        move(x+w+8,y+h+8);edge(1);move(x+208+8,y+128+8);edge(0);settled()
        move(630,230);s.cells('text-gadget-minimum')
        x,y,w,h=[s.number(a+F['work']+i*2,2) for i in range(4)]
        count=s.number(a+F['document']+12,2);rows=s.number(a+F['rows'],2)
        first=s.number(a+F['first'],2);extent=count-rows
        height=h-32;thumb=max(8,height*(rows*1000//count)//1000)
        top=y+16+(height-thumb)*(first*1000//extent)//1000
        print('Viewer thumb',dict(work=[x,y,w,h],count=count,rows=rows,first=first,top=top,thumb=thumb),flush=True)
        move(x+w+8,top+thumb//2);edge(1);move(x+w+8,y+h-16);edge(0);settled()
        require(s.number(a+F['first'],2)==extent,'Thumb did not reach last page')
        move(630,230);s.cells('text-gadget-bottom');menus.close();collected()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);args=p.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=Gadgets(),profile_commands=False)
    (out/'text-gadgets-results.json').write_text(json.dumps(result,indent=2)+'\n')
