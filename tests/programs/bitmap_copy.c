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

#include <hardware/vbxe-snapshots.h>
/* Packed capture/restore through both reserved slots, including all slot slack. */
void CopySnapshots(void)
{
    UWORD slot,large,y,x,width,height,pitch,good,n,launches;
    ULONG base,used,offset,id;
    for (slot=0;slot<2;slot++) for (large=0;large<2;large++) {
        base=slot ? DESKTOP_SNAPSHOT_1_BASE : DESKTOP_SNAPSHOT_0_BASE;
        width=large ? 630 : 528; height=large ? 208 : 184;
        pitch=width/2; used=(ULONG)pitch*height;
        memset(buffer,0xa5,sizeof(buffer));
        check(VbxeWrite(&display,base-16,buffer,16)==DISPLAY_OK);
        check(VbxeWrite(&display,base+DESKTOP_SNAPSHOT_BYTES,buffer,16)==DISPLAY_OK);
        for (offset=0;offset<DESKTOP_SNAPSHOT_BYTES;offset+=sizeof(buffer))
            check(VbxeWrite(&display,base+offset,buffer,sizeof(buffer))==DISPLAY_OK);
        for (y=0;y<240;y++) {
            for (x=0;x<320;x++) buffer[x]=(UBYTE)(x+y);
            check(VbxeWrite(&display,(ULONG)y*320,buffer,320)==DISPLAY_OK);
        }
        memset(&request,0,sizeof(request));
        request.source.pitch=320; request.source.width=640; request.source.height=240;
        request.destination.offset=base; request.destination.pitch=pitch;
        request.destination.width=request.width=width;
        request.destination.height=request.height=height;
        launches=scrollLaunches;
        check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id);
        check(scrollLaunches==launches+1 && VbxeFence(&display)==DISPLAY_OK);
        for (y=0;y<height;y++) {
            check(VbxeRead(&display,base+(ULONG)y*pitch,buffer,pitch)==DISPLAY_OK);
            good=1; for (x=0;x<pitch;x++) if (buffer[x]!=(UBYTE)(x+y)) good=0;
            check(good);
        }
        for (offset=used;offset<DESKTOP_SNAPSHOT_BYTES;offset+=n) {
            n=(UWORD)((DESKTOP_SNAPSHOT_BYTES-offset)>sizeof(buffer) ? sizeof(buffer) : DESKTOP_SNAPSHOT_BYTES-offset);
            check(VbxeRead(&display,base+offset,buffer,n)==DISPLAY_OK);
            good=1; for (x=0;x<n;x++) if (buffer[x]!=0xa5) good=0;
            check(good);
        }
        check(VbxeRead(&display,base-16,buffer,16)==DISPLAY_OK);
        check(VbxeRead(&display,base+DESKTOP_SNAPSHOT_BYTES,buffer+16,16)==DISPLAY_OK);
        good=1; for (x=0;x<32;x++) if (buffer[x]!=0xa5) good=0;
        check(good);
        check(VbxeFill(&display,0,320,320,240,0)==DISPLAY_OK);
        request.source=request.destination;
        request.destination.offset=0; request.destination.pitch=320;
        request.destination.width=640; request.destination.height=240;
        launches=scrollLaunches;
        check(VbxeCopyStart(&display,&request,&id)==DISPLAY_OK && id);
        check(scrollLaunches==launches+1 && VbxeFence(&display)==DISPLAY_OK);
        for (y=0;y<240;y++) {
            check(VbxeRead(&display,(ULONG)y*320,buffer,320)==DISPLAY_OK);
            good=1;
            for (x=0;x<320;x++)
                if (buffer[x]!=(UBYTE)(x<pitch && y<height ? x+y : 0)) good=0;
            check(good);
        }
    }
}
