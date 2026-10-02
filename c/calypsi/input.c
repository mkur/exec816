#include <exec/input.h>

/* Bound by the native launcher before C Tasks are admitted. All addresses
 * cross as full huge values; native wrappers validate before narrowing. */
void EXEC_PTR *ExecInputEntries[8];
struct InputArgs { ULONG lease, address, value; };
UWORD EXEC_CALL _InputCall(UWORD entry, const struct InputArgs *args);

static UWORD call(UWORD entry, struct InputLease *lease, const void *address, ULONG value)
{
    struct InputArgs args = {(ULONG)lease, (ULONG)address, value};
    return _InputCall(entry*3, &args);
}
UWORD InputAcquire(struct InputLease *p, const struct InputConfig *c) { return call(0,p,c,0); }
UWORD InputCreateRoute(struct InputLease *p, UWORD flags, ULONG *tag) { return call(1,p,tag,flags); }
UWORD InputPublishRoute(struct InputLease *p, ULONG tag) { return call(2,p,NULL,tag); }
UWORD InputRetireRoute(struct InputLease *p, ULONG tag) { return call(3,p,NULL,tag); }
UWORD InputDiscard(struct InputLease *p, ULONG tag) { return call(4,p,NULL,tag); }
UWORD InputPending(struct InputLease *p, UWORD *mask) { return call(5,p,mask,0); }
UWORD InputTake(struct InputLease *p, struct InputEvent *event) { return call(6,p,event,0); }
UWORD InputRelease(struct InputLease *p) { return call(7,p,NULL,0); }
