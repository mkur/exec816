"""Public input waits with controlled presenter and alarm-retirement races."""
from library_paths import read_source
from native_program import ROOT, require
from test_aes_inbox import producer as inbox_producer


def producer(out, symbols):
    inbox_producer(out, symbols)
    path = out/'aesinboxprobe.act'
    source = path.read_text()
    source = source.replace('  LET service=AESSTATE.Get()', '\n'.join(
        f'  LET {n.lower()}=CARD POINTER(${symbols["AESInput"+n]:x})'
        for n in ('X', 'Y', 'Key', 'Modifiers'))+'\n  LET service=AESSTATE.Get()')
    source = source.replace('sample.x=INT(index)', 'sample.x=INT(x^)+INT(index)')
    source = source.replace('sample.y=-INT(index)', 'sample.y=INT(y^)-INT(index)')
    source = source.replace('sample.qualifiers=2', 'sample.qualifiers=modifiers^')
    source = source.replace('sample.key=INT($100+index)', 'sample.key=INT(key^+index)')
    source = source.replace('  WHEN 4 THEN', '''  WHEN 9 THEN
    client.endpoint.input.keyHead=250
    client.endpoint.input.keyTail=250
    client.endpoint.input.buttonHead=250
    client.endpoint.input.buttonTail=250

  WHEN 8 THEN
    sample.x=INT(x^)
    sample.y=INT(y^)
    sample.buttons=buttons^
    sample.qualifiers=modifiers^
    AESINBOX.Snapshot(client,@sample,eligible^)

  WHEN 4 THEN''')
    path.write_text(source)


def caller(out):
    source = (ROOT/'c/calypsi/aes-events.c').read_text().replace(
        '#include "aes-private.h"', '#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\n'
        'void AESBeforeWait(struct ExecAESContext *c, ULONG mask);\n'
        'void AESBeforeSend(struct ExecAESContext *c);\n'
        'void AESBeforeCancel(struct ExecAESContext *c);\n'
        'void AESAfterRead(struct ExecAESContext *c);\n')
    for old, new in (
        ('    return TRUE;\nfailure:', '    AESAfterRead(c);\n    return TRUE;\nfailure:'),
        ('        Wait(mask);', '        AESBeforeWait(c, mask);\n        Wait(mask);'),
        ('    SendIO(&t->alarm->tc_Request);', '    AESBeforeSend(c);\n    SendIO(&t->alarm->tc_Request);'),
        ('        t->state = AES_ALARM_RETIRING;', '        t->state = AES_ALARM_RETIRING;\n        AESBeforeCancel(c);')):
        require(source.count(old) == 1, 'Input wait boundary changed: '+old)
        source = source.replace(old, new)
    (out/'aes-events.c').write_text(source)
    core = read_source(ROOT/'lib/aes/aescore.act')
    needle = '  IF request.message.mn_Length<>AESTYPES.REQUEST_SIZE THEN'
    require(core.count(needle) == 1, 'AES dispatch boundary changed')
    core = core.replace(needle, '''  IF request.operation=AESTYPES.OP_KEYBD
      OR request.operation=AESTYPES.OP_BUTTON OR request.operation=AESTYPES.OP_MULTI
      OR request.operation=AESTYPES.OP_MESAG OR request.operation=AESTYPES.OP_TIMER THEN
    HEAPCORE.Abort($fcc3)
  FI

'''+needle)
    (out/'aescore.act').write_text(core)
