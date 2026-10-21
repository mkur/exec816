#!/usr/bin/env python3
"""Real idle blinking must touch only the caret band, with matching text pixels."""
import argparse
import json
import struct
from pathlib import Path
from native_program import ROOT, require
from test_qed_selection import run
from test_qed_documents import fixtures
from qed_saving_observe import SavingEditor
from qed_viewport_observe import peer_pixels
from generate_aes_server import expected_layout

TEXT=b'the cursor should blink without repainting this line\nsecond line'


def interact(b,p,app,record,owner):
    e=SavingEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        lines=TEXT.split(b'\n');e.launched('cursor-launch',lines,len(TEXT),path=b'D1:LONG.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'))
        e.click(100,44);e.move(630,20)
        for index in range(4):
            e.caret_pixels('idle-visible-'+str(index),lines,0,0)
            t=e.text()['pointer'];depth=e.context()+dict(expected_layout())['C context updateDepth']
            e.reach('(db($%x)=1)&(dw($%x)=0)'%(t+e.offsets[23],depth));e.frames(2)
            state=e.text();require(state['blink']==1,'Hidden caret checkpoint changed')
            e.scene.setdefault('hidden_carets',[]).append(e.pixels('idle-hidden-'+str(index),lines,state,caret=True))
        require(e.get(e.sy['QedCursorWideDraws'])==0,'Cursor repainted outside its band')
        require(e.get(e.sy['QedCursorGlyphs'])>=4,'Idle blink did not restore its underlying glyph')
        e.peer_command(2);e.frames(40);e.covered=[(0,60,224,172)]
        e.selection('cursor-covered',lines,None,0,0);peer_pixels(e,'cursor-peer')
        e.frames(120);peer_pixels(e,'cursor-peer-idle')
        e.click(100,44);e.covered=[];e.frames(40)
        e.caret_pixels('cursor-exposed',lines,0,0)
        e.select('cursor-selection',lines,e.cell(0,0),e.cell(4,0),(0,0,0,4),(4,0))
        e.key('ESC');e.expected_range=None;e.caret_pixels('cursor-after-selection',lines,4,0)
        require(e.get(e.sy['QedCursorWideDraws'])==0,'Selection/exposure widened caret drawing')
        e.scene['caret_draws']=dict(bars=e.get(e.sy['QedCursorBars']),glyphs=e.get(e.sy['QedCursorGlyphs']),
            outside_band=e.get(e.sy['QedCursorWideDraws']),idle_transitions=8)
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101));e.click(100,44)
        return e.retire_key('Q',ctrl=True)
    if cycle==1:e.form_open();e.alert(1);e.loaded('cursor-missing-launch',[b''])
    elif cycle==2:e.launched('cursor-deep-launch',[b'deep'],4,path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT')
    else:
        e.launched('cursor-stop-launch',[b'one',b'last'],9,ending=0,path=b'D1:CRLF.TXT');e.key('A')
        b.memload(e.at('control'),struct.pack('<H',4));e.reach('dw($%x)=104'%e.at('phase'))
        e.form_open();e.alert(3);e.command_idle()
        b.memload(e.at('control'),struct.pack('<H',104));return e.alert(2,retiring=True)
    b.memload(e.at('control'),struct.pack('<H',cycle+1));return e.retire_key('Q',ctrl=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--native-from',type=Path,required=True)
    a=parser.parse_args();files=fixtures();files['LONG.TXT']=TEXT
    r=run(a.output,native_from=a.native_from,fixture_source=ROOT/'tests/programs/qed_cleanup_stop.act',
        media_files=files,saving=True,caret=True,writable=True,interaction=interact)
    print(r['status'],r['completed'])
