#!/usr/bin/env python3
"""AW5 load fixture: an unchanged production panel plus test-owned form/control."""
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT


def fixture(out):
    out.mkdir(parents=True, exist_ok=True)
    source = (ROOT/'tests/programs/desktop_input.act').read_text()
    source = source.replace('USE REGIONS\n', 'USE REGIONS\nUSE DESKAPP\nUSE WIDGETTYPES\nUSE A816MEMORY\n')
    source = source.replace('BYTE holdEvents', 'WIDGETTYPES.Tree tree\nBYTE holdEvents')
    source = source.replace('  ready=1\n', '''  Require(DESKAPP.Start()<>0)
  ready=1
''')
    source = source.replace('  Send(DESKTYPES.CLOSE,panel)', '  DESKAPP.Stop()\n  Send(DESKTYPES.CLOSE,panel)')
    source = source.replace('control.value=DESKTYPES.CONTENT_COMMANDS', 'control.value=DESKTYPES.CONTENT_WIDGETS')
    source = source.replace('440,80,624,224', '48,56,248,136')
    source = source.replace('  previousMode=0', '''  tree.version=WIDGETTYPES.VERSION
  tree.count=2
  tree.textBytes=7
  tree.background=8
  tree.objects(0).next=-1
  tree.objects(0).head=1
  tree.objects(0).tail=1
  tree.objects(0).kind=WIDGETTYPES.G_BOX
  tree.objects(0).spec=$78
  tree.objects(0).width=184
  tree.objects(0).height=56
  tree.objects(1).next=0
  tree.objects(1).head=-1
  tree.objects(1).tail=-1
  tree.objects(1).kind=WIDGETTYPES.G_BUTTON
  tree.objects(1).flags=WIDGETTYPES.FLAG_SELECTABLE OR WIDGETTYPES.FLAG_LAST
  tree.objects(1).x=8
  tree.objects(1).y=16
  tree.objects(1).width=72
  tree.objects(1).height=16
  A816MEMORY.Move(@tree.text(0),BYTE POINTER(c"Second"),7)
  DESKTOP.Prepare(@control,DESKTYPES.SET_TREE)
  control.payload=BYTE POINTER(@tree)
  control.bytes=WIDGETTYPES.TREE_SIZE
  Send(DESKTYPES.SET_TREE,panel)
  previousMode=0''')
    # A test-only matched full-redraw control. There is one production client;
    # this switch deliberately replaces its otherwise identical label patch.
    app = (ROOT/'lib/desktop/deskapp.act').read_text().replace('CARD updates\n', 'CARD updates\nBYTE benchmarkFull\n')
    needle='  DESKTOP.Prepare(@control,DESKTYPES.UPDATE_WIDGETS)'
    app=app.replace(needle, '''  IF benchmarkFull<>0 THEN
    BEGIN
      CARD index

      A816MEMORY.Clear(BYTE POINTER(tree),WIDGETTYPES.TREE_SIZE)
      BuildTree()
      FOR index=0 TO 7 DO
        tree.objects(index).state=snapshot.objects(index).state
      OD

      Label(OBJ_STATUS,CSTRING(@patch.text(0)),patch.changes(0).length)
      DESKTOP.Prepare(@control,DESKTYPES.SET_TREE)
      control.window=windowId
      control.payload=BYTE POINTER(tree)
      control.bytes=WIDGETTYPES.TREE_SIZE
      IF Call(DESKTYPES.SET_TREE)<>DESKTYPES.OK THEN
        HEAPCORE.Abort($faf8)
      FI

      refresh=0
      RETURN
    END
  FI

'''+needle)
    (out/'deskapp.act').write_text(app)
    fixture=out/'fixture.act';fixture.write_text(source)
    return fixture


def build(out, aes=False):
    source=fixture(out)
    return build_bitmap(source, out, True, desktop=True, aes=aes, stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2)])


if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    build(a.parse_args().output.resolve())
