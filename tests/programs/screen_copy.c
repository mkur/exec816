/* Actual copy encoders; capture BCBs for the host's independent pixel oracle. */
#include "vbxe-internal.h"
#include <exec816/vdi-unit.h>
#include <string.h>
#include "screen-copy-cases.h"

struct Result { UWORD status,enters,leaves,submits,unexpected; UBYTE records[16*21]; };
volatile struct Result ScreenCopyResults[SCREEN_COPY_CASES];
static struct Result *result;
static struct VbxeDisplay display;
static struct DisplayGrant grant;
static struct VbxeCopy request;
static ULONG GemScreenRows[240];
static UWORD fault,entryStatus,submitStatus;
static UBYTE edges[480];

UWORD DisplayEnter(struct DisplayGrant *g)
{ (void)g; ++result->enters; return entryStatus; }
UWORD DisplayLeave(struct DisplayGrant *g)
{ (void)g; ++result->leaves; return DISPLAY_OK; }
static void pointer_erase(UWORD l,UWORD t,UWORD r,UWORD b)
{ (void)l;(void)t;(void)r;(void)b; }
static void latch(UWORD status) { if (status && !fault) fault=status; }
static UWORD fence_owner(void) { return fault; }
static UWORD borrow_leave(struct DisplayGrant *g) { DisplayLeave(g);return fault; }
static void blit_mask(ULONG a,UWORD b,ULONG c,UWORD d,UWORD e,UWORD f,UBYTE g,UBYTE h,UBYTE i)
{ (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;(void)i;++result->unexpected; }
static void blit_and(ULONG a,UWORD b,UWORD c,UWORD d,UBYTE e)
{ (void)a;(void)b;(void)c;(void)d;(void)e;++result->unexpected; }
UWORD VbxeOwnerRead(struct VbxeDisplay *d,ULONG a,void *p,UWORD n)
{ (void)d;(void)a;(void)p;(void)n;++result->unexpected;return DISPLAY_DEVICE_FAULT; }
UWORD VbxeOwnerWrite(struct VbxeDisplay *d,ULONG a,const void *p,UWORD n)
{ (void)d;(void)a;(void)p;(void)n;++result->unexpected;return DISPLAY_DEVICE_FAULT; }
static UWORD submit(struct VbxeDisplay *d,const UBYTE *p,UWORD n)
{
    (void)d;
    if (n!=1 || result->submits>=16) { ++result->unexpected;return DISPLAY_BAD_ARGUMENT; }
    memcpy(result->records+result->submits*21,p,21);
    ++result->submits;
    return submitStatus;
}

#include "screen-copy-driver.inc"
#include "screen-copy-renderer.inc"

LONG ScreenCopyProbe(void)
{
    UWORD i;
    for (i=0;i<240;++i) GemScreenRows[i]=(ULONG)i*320;
    for (i=0;i<SCREEN_COPY_CASES;++i) {
        result=(struct Result *)&ScreenCopyResults[i];
        memset(result,0,sizeof(*result));
        memcpy(&request,screenCases[i].packet,sizeof(request));
        fault=0;entryStatus=screenCases[i].entryStatus;submitStatus=screenCases[i].submitStatus;
        result->status=screenCases[i].direct ? VbxeOwnerCopyRect(&display,&request)
            : GemDrawingCopyBorrow(&grant,&request,edges);
        if (memcmp(&request,screenCases[i].packet,sizeof(request))) ++result->unexpected;
    }
    return 0;
}
int main(void) { return 0; }
