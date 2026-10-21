"""Stop during staged writing and after publication before large E reclamation."""
import struct
from native_program import require
from qed_saving_observe import SavingEditor


def large_stop(e):
    b=e.b
    e.launched('large-cleanup-stop-launch',[b'one',b'last'],9,ending=0,path=b'D1:CRLF.TXT');e.key('A')
    before=e.get(e.sy['QedSaveWriteCalls']);e.put('QedSaveHoldWrite',1)
    e.key('S',ctrl=True);e.consents(backup=True);e.write_held(before)
    b.memload(e.at('control'),struct.pack('<H',4));e.reach('dw($%x)=104'%e.at('phase'))
    e.put('QedSaveHoldWrite',0);e.form_open();e.alert(3);e.command_idle()
    e.selection('large-cleanup-staging-stop-cancel',[b'aone',b'last'],None,1,0)
    before=e.get(e.sy['QedSaveDeleteEntered']);e.put('QedSaveHoldDelete',1)
    e.key('S',ctrl=True);e.consents(backup=True)
    e.reach('dw($%x)!=%d'%(e.sy['QedSaveDeleteEntered'],before),timeout=240)
    active=e.get(e.sy['active_save'],4)
    layout=struct.unpack('<14H',b.memdump(e.sy['QedSavingLayout'],28))
    require(e.get(active+layout[9])==1,'Large E cleanup began before publication')
    e.put('QedSaveHoldDelete',0)
    e.reach('(dw($%x)=5)&(db($%x)=4)'%(active+layout[7],e.task+e.extra[3]),timeout=240)
    start=b.eval_expr('@clk');b.memload(e.at('control'),struct.pack('<H',104))
    e.reach('dw($%x)=2'%e.at('stopCount'))
    e.scene['large_cleanup_stop']=dict(older_backup_bytes=262144,volume_sectors=2880,
        stop_requests=2,clock_during_delete=start,native_delete_pending=True,
        scope='Caller blocked in native reclamation; volume bound, no 4 KiB frame deadline')


def interact(b,p,app,record,owner):
    e=SavingEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        e.launched('cleanup-stop-launch',[b'd'],1,path=b'D1:LONG.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101));e.click(100,44)
        return e.retire_key('Q',ctrl=True)
    if cycle==1:e.form_open();e.alert(1);e.loaded('cleanup-stop-missing-launch',[b''])
    elif cycle==2:e.launched('cleanup-stop-deep-launch',[b'deep'],4,path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT')
    else:return large_stop(e)
    b.memload(e.at('control'),struct.pack('<H',cycle+1));return e.retire_key('Q',ctrl=True)
