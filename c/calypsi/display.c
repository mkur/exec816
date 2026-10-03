#include <exec/display.h>
#include <hardware/vbxe-notify.h>

/* The native launcher binds the ordinary library before admitting C Tasks. */
void EXEC_PTR *ExecDisplayEntries[15];
struct DisplayArgs { ULONG lease; UWORD kind; };
ULONG EXEC_CALL _DisplayCall(UWORD entry, const struct DisplayArgs *args);

static UWORD call(UWORD entry, struct DisplayLease *lease, UWORD kind)
{
    struct DisplayArgs args = {(ULONG)lease,kind};
    return _DisplayCall(entry*3,&args);
}
UWORD DisplayAcquire(struct DisplayLease *p,UWORD kind) { return call(0,p,kind); }
UWORD DisplayActivate(struct DisplayLease *p) { return call(1,p,0); }
UWORD DisplayCheck(struct DisplayLease *p) { return call(2,p,0); }
UWORD DisplayBeginRelease(struct DisplayLease *p) { return call(3,p,0); }
UWORD DisplayRelease(struct DisplayLease *p) { return call(4,p,0); }
UWORD DisplayFault(struct DisplayLease *p) { return call(5,p,0); }
UWORD DisplayBaseline(void) { return call(6,NULL,0); }
UWORD DisplayTicks(void) { return call(7,NULL,0); }
void DisplayResetRequired(void) { call(8,NULL,0); }

UWORD VbxeNotifyOpen(struct DisplayLease *p) { return call(9,p,0); }
UWORD VbxeNotifyClose(struct DisplayLease *p) { return call(10,p,0); }
ULONG VbxeNotifyMask(struct DisplayLease *p)
{
    struct DisplayArgs args = {(ULONG)p,0};
    return _DisplayCall(11*3,&args);
}
UWORD VbxeNotifyArm(ULONG id)
{
    struct DisplayArgs args = {id,0};
    return _DisplayCall(12*3,&args);
}
UWORD VbxeNotifyState(ULONG id)
{
    struct DisplayArgs args = {id,0};
    return _DisplayCall(13*3,&args);
}
void VbxeNotifyReset(void) { call(14,NULL,0); }
