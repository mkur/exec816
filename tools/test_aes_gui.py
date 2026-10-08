"""Emitted presenter-side GUI producer for the focused AES service fixture."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    source = '''MODULE AESGUIPROBE
USE EXEC
USE AESSTATE
USE AESTYPES
USE AESGUI
USE HEAPCORE

PUBLIC PROC Pump()

  LET command=CARD POINTER($COMMAND)
  IF command^=0 THEN
    RETURN
  FI

  LET identity=LONGCARD POINTER($CLIENT)
  LET service=AESSTATE.Get()
  LET client=AESSTATE.Find(service,identity^)
  IF client=NULL THEN
    HEAPCORE.Abort($fcb0)
  FI

  IF command^=1 THEN
    IF AESGUI.Open(service,client,7)=0 THEN
      HEAPCORE.Abort($fcb1)
    FI
  ELSEIF command^=2 THEN
    AESGUI.Post(service,client,AESTYPES.GUI_REDRAW,10,20,30,40)
    AESGUI.Post(service,client,AESTYPES.GUI_REDRAW,100,30,10,10)
    AESGUI.Post(service,client,AESTYPES.GUI_TOPPED,0,0,0,0)
    AESGUI.Post(service,client,AESTYPES.GUI_REDRAW,90,25,5,20)
    AESGUI.Post(service,client,AESTYPES.GUI_MOVED,21,31,100,100)
    AESGUI.Post(service,client,AESTYPES.GUI_CLOSED,0,0,0,0)
    AESGUI.Post(service,client,AESTYPES.GUI_MOVED,31,41,100,100)
  ELSEIF command^=3 THEN
    AESGUI.Post(service,client,AESTYPES.GUI_REDRAW,1,1,8,8)
    AESGUI.Close(client)
    IF AESGUI.Open(service,client,8)=0 THEN
      HEAPCORE.Abort($fcb2)
    FI

    AESGUI.Post(service,client,AESTYPES.GUI_REDRAW,110,120,10,11)
  FI

  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,LONGCARD(1) LSH client.endpoint.port.mp_SigBit)
  EXEC.Permit()

RETURN
ENDMODULE
'''.replace('$COMMAND', f'${symbols["AESGuiCommand"]:x}').replace(
    '$CLIENT', f'${symbols["AESGuiClient"]:x}')
    (out/'aesguiprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act')
    host = host.replace('USE AESCORE', 'USE AESCORE\nUSE AESGUIPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'GUI producer wake boundary changed')
    host = host.replace(needle, '  AESGUIPROBE.Pump()\n'+needle)
    (out/'aeshost.act').write_text(host)
