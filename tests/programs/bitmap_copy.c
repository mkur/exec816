#include <hardware/vbxe.h>
#include <string.h>
#include "bitmap-copy-cases.h"
extern struct VbxeDisplay display;
extern volatile UWORD fault_arm,ProbeStopped,variant;
extern volatile UWORD ownerChecks;
volatile UWORD copyCase,copyChecks,copyFailures,copyFirstFailure,copyChunks,copyFaultAfter;
static UBYTE buffer[8192];
static struct VbxeCopy request;

void ProbeCopyChunk(void)
{
    ++copyChunks;
    if (copyFaultAfter && copyChunks==copyFaultAfter) fault_arm=1;
}
static void check(UWORD good)
{
    ++copyChecks;
    if (!good) { if (!copyFailures) copyFirstFailure=copyCase+1; ++copyFailures; }
}
void CopyCases(void)
{
    UWORD i,status,before;
    ULONG hash;
    const struct CopyCase *c;
    check(VbxeCopyRect(&display,NULL)==DISPLAY_BAD_ARGUMENT);
    check(VbxeCopyRect(&display,(void *)0xffffffUL)==DISPLAY_BAD_ARGUMENT);
    check(VbxeCopyRect(&display,(void *)0x8000UL)==DISPLAY_BAD_ARGUMENT);
    for (copyCase=0;copyCase<sizeof(copyCases)/sizeof(copyCases[0]);++copyCase) {
        c=&copyCases[copyCase];
        if (c->fault && variant!=11) continue;
        for (i=0;i<sizeof(buffer);i++) buffer[i]=(UBYTE)(i*37+(i>>8)*11);
        check(VbxeWrite(&display,c->base,buffer,sizeof(buffer))==DISPLAY_OK);
        memcpy(&request,c->packet,sizeof(request));
        copyChunks=0; copyFaultAfter=c->fault; ProbeStopped=0;
        before=ownerChecks;
        status=VbxeCopyRect(&display,&request);
        check((UWORD)(ownerChecks-before)==1);
        check(status==c->status);
        if (c->fault) {
            check(copyChunks==1 && display.lease.state==DISPLAY_FREE);
            fault_arm=copyFaultAfter=0;
            check(VbxeOpen(&display)==DISPLAY_OK);
        }
        memset(buffer,0xa5,sizeof(buffer));
        check(VbxeRead(&display,c->base,buffer,sizeof(buffer))==DISPLAY_OK);
        hash=2166136261UL;
        for (i=0;i<sizeof(buffer);i++) hash=(hash^buffer[i])*16777619UL;
        check(hash==c->hash);
    }
}
