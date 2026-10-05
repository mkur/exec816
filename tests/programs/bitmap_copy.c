#include <hardware/vbxe.h>
#include <string.h>
#include <proto/exec.h>
#include "bitmap-copy-cases.h"
extern struct VbxeDisplay display;
extern volatile UWORD fault_arm,ProbeStopped,variant;
extern volatile UWORD ownerChecks,scrollLaunches;
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
    UWORD i,status,before,launches,asynchronous=variant>=17;
    ULONG hash,id,untouched,previous=0;
    const struct CopyCase *c;
    check(VbxeCopyRect(&display,NULL)==DISPLAY_BAD_ARGUMENT);
    check(VbxeCopyRect(&display,(void *)0xffffffUL)==DISPLAY_BAD_ARGUMENT);
    check(VbxeCopyRect(&display,(void *)0x8000UL)==DISPLAY_BAD_ARGUMENT);
    if (asynchronous) {
        id=12345;
        check(VbxeCopyStart(&display,NULL,&id)==DISPLAY_BAD_ARGUMENT && id==12345);
        check(VbxeCopyStart(&display,&request,NULL)==DISPLAY_BAD_ARGUMENT);
    }
    for (copyCase=0;copyCase<sizeof(copyCases)/sizeof(copyCases[0]);++copyCase) {
        if (variant==18 && copyCase>0) break; /* Small compiler/descriptor probe. */
        c=&copyCases[copyCase];
        if (c->fault && variant!=11) continue;
        for (i=0;i<sizeof(buffer);i++) buffer[i]=(UBYTE)(i*37+(i>>8)*11);
        check(VbxeWrite(&display,c->base,buffer,sizeof(buffer))==DISPLAY_OK);
        memcpy(&request,c->packet,sizeof(request));
        copyChunks=0; copyFaultAfter=c->fault; ProbeStopped=0;
        before=ownerChecks;
        id=12345;
        launches=scrollLaunches;
        status=asynchronous ? VbxeCopyStart(&display,&request,&id)
                            : VbxeCopyRect(&display,&request);
        check((UWORD)(ownerChecks-before)==1);
        if (asynchronous && status==DISPLAY_OK) {
            if (id) {
                check(id>previous && scrollLaunches==launches+1);
                previous=id;
                untouched=12345;
                check(VbxeCopyStart(&display,NULL,&untouched)==DISPLAY_BUSY);
                check(VbxeScrollStart(&display,NULL,0,&untouched)==DISPLAY_BUSY);
                check(untouched==12345 && display.operationId==id);
                memset(&request,0xa5,sizeof(request)); /* No descriptor borrow. */
                check(VbxePoll(&display,id+1)==DISPLAY_BAD_ARGUMENT);
                check(VbxeFence(&display)==DISPLAY_OK);
                check(VbxePoll(&display,id)==DISPLAY_OK && !display.operationPending);
            } else check(scrollLaunches==launches);
        } else if (asynchronous) check(id==12345 && scrollLaunches==launches);
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

void CopyMaximum(void)
{
    ULONG id,old;
    UWORD y,i,launches;
    for (y=0;y<240;y++) {
        memset(buffer,(UBYTE)y,320);
        check(VbxeWrite(&display,(ULONG)y*320,buffer,320)==DISPLAY_OK);
    }
    memset(&request,0,sizeof(request));
    request.source.pitch=request.destination.pitch=320;
    request.source.width=request.destination.width=request.width=640;
    request.source.height=request.destination.height=request.height=240;
    request.destination.offset=0x10000UL;
    launches=scrollLaunches;
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id);
    check(scrollLaunches==launches+1);
    check(VbxeFence(&display)==DISPLAY_OK);
    for (y=0;y<240;y++) {
        check(VbxeRead(&display,0x10000UL+(ULONG)y*320,buffer,320)==DISPLAY_OK);
        for (i=0;i<320;i++) check(buffer[i]==(UBYTE)y);
    }
    request.height=241;
    old=id;
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_BAD_ARGUMENT && id==old);
    request.height=240;
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id>old);
    old=id;
    check(VbxeClose(&display)==DISPLAY_OK && !display.operationPending);
    check(VbxeOpen(&display)==DISPLAY_OK);
    check(VbxePoll(&display,old)==DISPLAY_BAD_ARGUMENT);
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id>old);
    check(VbxeFence(&display)==DISPLAY_OK);
}

/* Test-only sequence injection is emitted by the driver fixture generator. */
extern void ProbeCopySequence(void);
void CopyExhaustion(void)
{
    ULONG id=12345;
    memcpy(&request,copyCases[0].packet,sizeof(request));
    ProbeCopySequence();
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id==0xffffffffUL);
    check(VbxeFence(&display)==DISPLAY_OK);
    id=12345;
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_UNSUPPORTED && id==12345);
    check(VbxeClose(&display)==DISPLAY_OK && VbxeOpen(&display)==DISPLAY_OK);
    check(VbxeCopyStart(&display,&request,&id)==DISPLAY_UNSUPPORTED && id==12345);
}
