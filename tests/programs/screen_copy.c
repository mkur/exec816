/* Actual encoders and mask-list producer, with observed hardware boundaries. */
#include "vbxe-internal.h"
#include <exec816/vdi-unit.h>
#include <string.h>
#include "screen-copy-cases.h"
#include "gem-vbxe-tables.h"

enum { RAW=1,TYPED,READ,WRITE,LEAVE };
struct Event { UWORD kind; UBYTE bytes[24]; };
struct Result {
    UWORD status,enters,leaves,submits,unexpected,eventCount,rawLists,reads,writes;
    struct Event events[128];
};
volatile struct Result ScreenCopyResults;
static struct Result *result=(struct Result *)&ScreenCopyResults;
static struct VbxeDisplay display;
static struct DisplayGrant grant;
static struct VbxeCopy request;
static UWORD fault,entryAt,submitStatus,failAt,ioCount,active,dirty,direct;
static UWORD commandCount,commandWork,stripRedirect;
static ULONG stripOffset;
static UBYTE commands[VBXE_BCB_BYTES],*commandNext;

static struct Event *capture(UWORD kind)
{
    struct Event *e;
    if (result->eventCount>=128) { ++result->unexpected;return NULL; }
    e=&result->events[result->eventCount++];e->kind=kind;
    return e;
}
static UWORD boundary(void)
{ return ++ioCount==failAt ? DISPLAY_DEVICE_FAULT:DISPLAY_OK; }
UWORD DisplayEnter(struct DisplayGrant *g)
{
    (void)g;
    if (active) ++result->unexpected;
    if (++result->enters==entryAt) return DISPLAY_BUSY;
    active=1;return DISPLAY_OK;
}
UWORD DisplayLeave(struct DisplayGrant *g)
{
    (void)g;if (!active) ++result->unexpected;
    active=0;++result->leaves;capture(LEAVE);return DISPLAY_OK;
}
static void pointer_erase(UWORD l,UWORD t,UWORD r,UWORD b)
{ (void)l;(void)t;(void)r;(void)b; }
static void latch(UWORD status) { if (status && !fault) fault=status; }
UWORD VbxeOwnerFence(struct VbxeDisplay *d) { (void)d;return boundary(); }
UWORD VbxeOwnerRead(struct VbxeDisplay *d,ULONG a,void *p,UWORD n)
{
    (void)d;(void)a;(void)p;(void)n;++result->reads;++result->unexpected;
    return DISPLAY_BAD_ARGUMENT;
}
UWORD VbxeOwnerWrite(struct VbxeDisplay *d,ULONG a,const void *p,UWORD n)
{
    (void)d;(void)a;(void)p;(void)n;++result->writes;++result->unexpected;
    return DISPLAY_BAD_ARGUMENT;
}
UWORD VbxeOwnerSubmit(struct VbxeDisplay *d,const UBYTE *p,UWORD n)
{
    UWORD i;ULONG work=0;UWORD status=boundary();(void)d;++result->rawLists;
    if (!active || n>VBXE_LIST_RECORDS) ++result->unexpected;
    for (i=0;i<n;++i) {
        UWORD bytes=(p[i*21+12]|(UWORD)p[i*21+13]<<8)+1;
        UWORD rows=(UWORD)p[i*21+14]+1;
        struct Event *e;
        work+=(ULONG)bytes*rows*(p[i*21+20] ? 3:2);
        e=capture(RAW);if (e) memcpy(e->bytes,p+i*21,21);
    }
    if (work>VBXE_LIST_WORK) ++result->unexpected;
    return status;
}
static UWORD submit(struct VbxeDisplay *d,const UBYTE *p,UWORD n)
{
    struct Event *e;UWORD status=boundary();(void)d;
    if (n!=1 || (!active && !direct)) ++result->unexpected;
    e=capture(TYPED);if (e) memcpy(e->bytes,p,21);
    ++result->submits;
    return status ? status:submitStatus;
}

static void flush(void);
#include "screen-copy-mask.inc"
static void flush(void) { drain(); }
static UWORD fence_owner(void)
{
    if (fault) return DISPLAY_DEVICE_FAULT;
    flush();if (!fault) latch(VbxeOwnerFence(&display));
    return fault ? DISPLAY_DEVICE_FAULT:DISPLAY_OK;
}
static UWORD borrow_leave(struct DisplayGrant *g)
{ UWORD status=fence_owner();DisplayLeave(g);return status; }
#include "screen-copy-driver.inc"
#include "screen-copy-renderer.inc"

LONG EXEC_CALL ScreenCopyProbe(ULONG value)
{
    UWORD i=(UWORD)value,n;
    const struct MaskCase *mask;
    if (i>=SCREEN_COPY_CASES) return -1;
    memset(result,0,sizeof(*result));memset(commands,0,sizeof(commands));
    memcpy(&request,screenCases[i].packet,sizeof(request));
    fault=active=ioCount=commandCount=commandWork=0;commandNext=commands;
    entryAt=screenCases[i].entryAt;submitStatus=screenCases[i].submitStatus;
    failAt=screenCases[i].failAt;
    direct=screenCases[i].direct;
    if (direct==2) {
        mask=&screenCases[i].mask;
        result->status=DisplayEnter(&grant);
        for (n=0;n<mask->repeats && !fault;n++)
            blit_mask(mask->source,mask->ss,mask->dest,mask->ds,
                      mask->bytes,mask->rows,mask->am,mask->xm,mask->mode);
        result->status=borrow_leave(&grant);
    } else {
        result->status=direct ? VbxeOwnerCopyRect(&display,&request)
            : GemDrawingCopyBorrow(&grant,&request);
    }
    if (memcmp(&request,screenCases[i].packet,sizeof(request)) || active) ++result->unexpected;
    return 0;
}
int main(void) { return 0; }
