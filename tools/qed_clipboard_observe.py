"""QE4 physical menu/key operations with independent ring and pixel oracles."""
import struct
from native_program import require
from qed_editing_observe import Editor
from qed_selection_observe import SelectionEditor

class ClipboardEditor(SelectionEditor):
    global_commands=('C','X','V','Z')
    pending_global=None
    def menu(self,title,item):
        before=self.get(self.sy['QedMenuCalls'])
        super().menu(title,item)
        self.reach('dw($%x)!=%d'%(self.sy['QedMenuCalls'],before))
        require(self.get(self.sy['QedMenuLastItem'])==self.ids[item],'Wrong menu command')
    def key(self,name,ctrl=False,**options):
        if ctrl and name in self.global_commands:
            before=self.get(self.sy['QedGlobalKeyCalls'])
            dialog=options.pop('dialog',False)
            options['dispatch']=False
            Editor.key(self,name,ctrl=True,**options)
            if dialog:self.pending_global=before
            else:self.reach('dw($%x)!=%d'%(self.sy['QedGlobalKeyCalls'],before))
            return
        return super().key(name,ctrl=ctrl,**options)
    def alert(self,*args,**options):
        result=super().alert(*args,**options)
        if self.pending_global is not None:
            self.reach('dw($%x)!=%d'%(self.sy['QedGlobalKeyCalls'],self.pending_global))
            self.pending_global=None
        return result
    def clipboard(self,expected):
        o=self.offsets;ring=self.sy['clip_text'];n=self.get(ring+o[17],4)
        line=self.get(ring+o[15]+o[13],4);actual=[]
        require(0<n<10000,'Invalid clipboard line count')
        for _ in range(n):
            actual.append(self.b.memdump(line+o[12],self.get(line+o[14])))
            line=self.get(line+o[13],4)
        require(line==ring+o[16] and actual==expected,'Clipboard bytes/ring differ')
        self.scene.setdefault('clipboard',[]).append([v.hex() for v in actual])

def interact(b,p,app,record,owner):
    e=ClipboardEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(60)
    e.selection('clipboard-empty',[b''],None,0,0);e.clipboard([b''])
    if cycle==0:
        for key in ('A','B','TAB','C','D','RETURN','RETURN','E','F','G','H'):e.key(key)
        lines=[b'ab\tcd',b'',b'efgh'];span=(0,1,2,2)
        e.select('copy-range',lines,e.cell(1,0),e.cell(2,2),span,(2,2))
        e.key('C',ctrl=True);e.selection('shortcut-copy',lines,span,2,2)
        clip=[b'b\tcd',b'',b'ef'];e.clipboard(clip)
        e.key('X',ctrl=True);e.selection('shortcut-cut',[b'agh'],None,1,0);e.clipboard(clip)
        e.key('Z',ctrl=True);e.selection('undo-cut',lines,span,2,2);e.clipboard(clip)
        e.key('Z',ctrl=True);e.selection('undo-toggle-cut',[b'agh'],None,1,0)
        e.key('V',ctrl=True);e.selection('shortcut-paste',lines,None,2,2)
        e.key('Z',ctrl=True);e.selection('undo-paste',[b'agh'],None,1,0)
        e.key('Z',ctrl=True);e.selection('undo-toggle-paste',lines,None,2,2)
        e.select('newline-range',lines,e.cell(10,0),e.cell(0,1),(0,5,1,0),(0,1))
        e.menu('TEDIT','MCOPY');e.clipboard([b'',b''])
        e.menu('TEDIT','MCUT');e.selection('menu-cut-newline',[b'ab\tcd',b'efgh'],None,5,0)
        e.menu('TEDIT','MPASTE');e.selection('menu-paste-newline',lines,None,0,1)
        e.menu('TEDIT','MUNDO');e.selection('menu-undo', [b'ab\tcd',b'efgh'],None,5,0)
        e.menu('TEDIT','MUNDO');e.selection('menu-toggle',lines,None,0,1)
        # Failure during clipboard replacement and after Cut's completed copy.
        e.select('failure-range',lines,e.cell(1,0),e.cell(2,2),span,(2,2))
        e.b.memload(e.sy['QedEditFailLine'],struct.pack('<H',2))
        e.key('C',ctrl=True,dialog=True);e.alert(1)
        e.selection('clipboard-allocation-rollback',lines,span,2,2);e.clipboard([b'',b''])
        e.b.memload(e.sy['QedEditFailLine'],struct.pack('<H',4))
        e.key('X',ctrl=True,dialog=True);e.alert(1)
        e.selection('cut-allocation-rollback',lines,span,2,2);e.clipboard([b'',b''])
        e.key('Y');e.selection('typed-selection-replacement',[b'aygh'],None,2,0)
        e.key('Z',ctrl=True);e.selection('undo-selection-replacement',lines,span,2,2)
        e.key('ESC');e.expected_range=None
        e.caret_pixels('clipboard-caret',lines,2,2)
    elif cycle==1:
        for key in ('A','B','C'):e.key(key)
        e.key('Z',ctrl=True);e.selection('undo-typing-group',[b''],None,0,0)
        e.key('Z',ctrl=True);e.selection('toggle-typing-group',[b'abc'],None,3,0)
        e.key('Z',ctrl=True);e.key('X');e.key('Z',ctrl=True)
        e.selection('edit-invalidates-toggle',[b''],None,0,0)
    elif cycle==2:
        e.key('A');e.key('RETURN');e.key('B');e.key('A',ctrl=True);e.key('C',ctrl=True)
        e.clipboard([b'a',b'b']);e.key('X',ctrl=True)
        e.selection('cut-to-empty',[b''],None,0,0);e.key('V',ctrl=True)
        e.selection('paste-from-empty',[b'a',b'b'],None,1,1)
    else:
        e.key('A');e.selection('clipboard-stop-dirty',[b'a'],None,1,0)
    b.memload(e.at('control'),struct.pack('<H',cycle+1))
    if cycle==3:e.alert(2);e.selection('clipboard-stop-cancel',[b'a'],None,1,0)
    e.key('Q',ctrl=True);return e.alert(1,retiring=True)
