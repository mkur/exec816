#include <exec/display.h>

/* The native launcher binds the ordinary library before admitting C Tasks. */
void EXEC_PTR *ExecDisplayEntries[9];
struct DisplayArgs { ULONG lease; UWORD kind; };
UWORD EXEC_CALL _DisplayCall(UWORD entry, const struct DisplayArgs *args);

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
