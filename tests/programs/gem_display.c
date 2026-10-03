#include <hardware/vbxe.h>
#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <string.h>

volatile UWORD stage,variant,checks,failures,first_failure,job,answer,finished;
volatile UWORD progress[2], fault_arm, ProbeStopped, mapPoint, mapGate;
volatile ULONG checksum[2], pixelHash, tickAddress;
volatile UWORD waitStart,waitEnd,vcountReads;
volatile UWORD ownerChecks;
struct VbxeDisplay display,other;
static struct Task *parent,*renderer,*peer;
static struct TaskLease peerLease,rendererLease;
static UBYTE readback[320],crossing[32];
static UBYTE list[VBXE_BCB_BYTES];
static ULONG rootMask;
static BYTE rootBit;
static volatile UWORD retired;
extern void CopyCases(void);
extern volatile UWORD copyFailures;

static void check(UWORD good)
{
    ++checks;
    if (!good) { if (!failures) first_failure=checks; ++failures; }
}

/* Test-only read substitution: ordinary runs read real hardware; timeout cases
 * retain real Exec ticks, register writes and the complete recovery path. */
UBYTE ProbeBusy(void)
{
    if (fault_arm && variant!=5 && (variant==6 || !ProbeStopped)) return 3;
    return *(volatile UBYTE *)0xd653UL;
}
UBYTE ProbeVcount(void)
{
    if (fault_arm && variant==5) { vcountReads++; return 100; }
    return *(volatile UBYTE *)0xd40bUL;
}

static void compute(UWORD who)
{
    ULONG a=0x12345678UL+who,b=0x87654321UL-who;
    UWORD i;
    for (i=0;i<30000;i++) {
        a=((a<<1)^(a>>31))^b;
        b+=a^i;
        progress[who]=i+1;
    }
    checksum[who]=a^b;
}

void Peer(void)
{
    Wait(1);
    check(VbxeFence(&display)==DISPLAY_INVALID_OWNER);
    check(VbxeSubmit(&display,NULL,0)==DISPLAY_INVALID_OWNER);
    check(VbxeClose(&display)==DISPLAY_INVALID_OWNER);
    check(VbxeOpen(&other)==DISPLAY_BUSY);
    compute(0);
    Wait(1);
    Forbid();
    retired++;
    Signal(parent,rootMask);
    RemTask(NULL);
}

/* Invalid later records must not execute an earlier valid prefix. The valid
 * maximum list paints independently known bytes and guards the unused arena. */
static void lists(void)
{
    UWORD i,before;
    UBYTE *r;
    memset(list,0,sizeof(list));
    before=ownerChecks;
    check(VbxeSubmit(&display,NULL,0)==DISPLAY_OK);
    check((UWORD)(ownerChecks-before)==1);
    check(VbxeSubmit(&display,NULL,1)==DISPLAY_BAD_ARGUMENT);
    check(VbxeSubmit(&display,(UBYTE *)0x8000UL,1)==DISPLAY_BAD_ARGUMENT);
    check(VbxeSubmit(&display,(UBYTE *)0xffffffUL,1)==DISPLAY_BAD_ARGUMENT);
    check(VbxeSubmit(&display,list,65)==DISPLAY_BAD_ARGUMENT);
    for (i=0;i<64;i++) {
        r=list+i*21;
        r[5]=r[11]=1;
        r[6]=(UBYTE)(640+i); r[7]=2;
        r[16]=(UBYTE)(i+1);
    }
    memset(readback,0xa5,320);
    check(VbxeWrite(&display,640,readback,64)==DISPLAY_OK);
    check(VbxeWrite(&display,VBXE_BCB+64*21,readback,32)==DISPLAY_OK);
    list[21+20]=8;
    check(VbxeSubmit(&display,list,2)==DISPLAY_BAD_ARGUMENT);
    check(VbxeRead(&display,640,readback,64)==DISPLAY_OK);
    for (i=0;i<64;i++) check(readback[i]==0xa5);
    list[41]=0;
    list[12]=255; list[13]=1; list[14]=255;
    check(VbxeSubmit(&display,list,1)==DISPLAY_BAD_ARGUMENT);
    list[12]=list[13]=list[14]=0;
    list[8]=8;
    check(VbxeSubmit(&display,list,1)==DISPLAY_BAD_ARGUMENT);
    list[6]=0; list[7]=0x80; list[8]=3;
    check(VbxeSubmit(&display,list,1)==DISPLAY_BAD_ARGUMENT);
    list[6]=0x80; list[7]=2; list[8]=0;
    list[4]=0x10;
    check(VbxeSubmit(&display,list,1)==DISPLAY_BAD_ARGUMENT);
    list[4]=0;
    list[19]=128;
    check(VbxeSubmit(&display,list,1)==DISPLAY_BAD_ARGUMENT);
    list[19]=0;
    check(VbxeSubmit(&display,list,64)==DISPLAY_OK);
    check(VbxeRead(&display,640,readback,64)==DISPLAY_OK);
    for (i=0;i<64;i++) check(readback[i]==i+1);
    check(VbxeRead(&display,VBXE_BCB+64*21,readback,32)==DISPLAY_OK);
    for (i=0;i<32;i++) check(readback[i]==0xa5);
    /* The native uploader must carry the source across a CPU bank boundary. */
    {
        UBYTE *allocation=AllocMem(131072UL,MEMF_UPPER|MEMF_LINEAR);
        UBYTE *cross;
        check(allocation!=NULL);
        if (allocation) {
            cross=(UBYTE *)((((ULONG)allocation+65551UL)&0xffff0000UL)-16UL);
            memcpy(cross,list,42);
            check(VbxeWrite(&display,640,readback+64,2)==DISPLAY_OK);
            check(VbxeSubmit(&display,cross,2)==DISPLAY_OK);
            check(VbxeRead(&display,640,readback,2)==DISPLAY_OK);
            check(readback[0]==1 && readback[1]==2);
            FreeMem(allocation,131072UL);
        }
    }
    /* Tall, narrow list takes the widened extent/work arithmetic path. */
    memset(list,0,21);
    list[5]=list[11]=1; list[7]=4; list[9]=1; list[14]=255;
    list[16]=0x36;
    check(VbxeSubmit(&display,list,1)==DISPLAY_OK);
    check(VbxeRead(&display,1024,readback,256)==DISPLAY_OK);
    for (i=0;i<256;i++) check(readback[i]==0x36);
}

static void pattern(void)
{
    UWORD i,row,good,before;
    ULONG hash=2166136261UL;
    for (i=0;i<32;i++) crossing[i]=(UBYTE)(i*7+3);
    check(VbxeWrite(&display,0x7fff0UL,crossing,32)==DISPLAY_BAD_ARGUMENT);
    check(VbxeWrite(&display,0x1000,(void *)0x8000UL,1)==DISPLAY_BAD_ARGUMENT);
    check(VbxeWrite(&display,0x3fff0UL,crossing,32)==DISPLAY_OK);
    memset(readback,0,sizeof(readback));
    check(VbxeRead(&display,0x3fff0UL,readback,32)==DISPLAY_OK);
    check(!memcmp(readback,crossing,32));
    lists();
    memset(readback,0xa5,sizeof(readback));
    check(VbxeWrite(&display,VBXE_SCREEN_BYTES,readback,16)==DISPLAY_OK);
    check(VbxeWrite(&display,VBXE_XDL+12,readback,244)==DISPLAY_OK);
    check(VbxeWrite(&display,VBXE_BCB+21,readback,231)==DISPLAY_OK);
    check(VbxeFill(&display,0,320,0,240,0)==DISPLAY_BAD_ARGUMENT);
    check(VbxeFill(&display,0xffffffffUL,320,320,240,0)==DISPLAY_BAD_ARGUMENT);
    for (i=0;i<16;i++) {
        before=ownerChecks;
        check(VbxeFill(&display,(ULONG)i*20,320,20,240,(UBYTE)(i*17))==DISPLAY_OK);
        check((UWORD)(ownerChecks-before)==1);
    }
    before=ownerChecks;
    check(VbxePresent(&display)==DISPLAY_OK);
    check((UWORD)(ownerChecks-before)==1);
    compute(1);
    for (row=0;row<240;row++) {
        before=ownerChecks;
        check(VbxeRead(&display,(ULONG)row*320,readback,320)==DISPLAY_OK);
        check((UWORD)(ownerChecks-before)==1);
        good=1;
        for (i=0;i<320;i++) {
            if (readback[i]!=(UBYTE)((i/20)*17)) good=0;
            hash=(hash^readback[i])*16777619UL;
        }
        check(good);
    }
    pixelHash=hash;
    check(VbxeRead(&display,VBXE_SCREEN_BYTES,readback,16)==DISPLAY_OK);
    for (i=0;i<16;i++) check(readback[i]==0xa5);
    check(VbxeRead(&display,VBXE_XDL+12,readback,244)==DISPLAY_OK);
    for (i=0;i<244;i++) check(readback[i]==0xa5);
    check(VbxeRead(&display,VBXE_BCB+21,readback,231)==DISPLAY_OK);
    for (i=0;i<231;i++) check(readback[i]==0xa5);
}

void Renderer(void)
{
    struct DisplayLease copy;
    UWORD status,start;
    Signal(parent,rootMask);
    for (;;) {
        Wait(1);
        if (job==1) {
            answer=VbxeOpen(&display);
            if (answer==DISPLAY_OK) {
                copy=display.lease;
                check(DisplayCheck(&copy)==DISPLAY_INVALID_OWNER);
                check(DisplayRelease(&display.lease)==DISPLAY_INVALID_OWNER);
                check(VbxeOpen(&display)==DISPLAY_BUSY);
            }
        } else if (job==2) {
            if (variant==4 || variant==5 || variant==6 || variant==8) {
                fault_arm=1;
                if (variant==8) *(volatile UWORD *)tickAddress=0xfffe;
                waitStart=start=DisplayTicks();
                answer=variant==5 ? VbxeWaitFrame(&display) : VbxeFence(&display);
                waitEnd=DisplayTicks();
                check(answer==DISPLAY_DEVICE_FAULT);
                if (variant==5) check(vcountReads>1);
                check((UWORD)(DisplayTicks()-start)>=VBXE_WAIT_TICKS);
                check((UWORD)(DisplayTicks()-start)<32);
                check(!display.mutated && display.lease.state==DISPLAY_FREE);
                fault_arm=0;
            } else {
                if (variant>=10) { CopyCases(); check(!copyFailures); }
                pattern();
                answer=VbxeClose(&display);
                check(answer==DISPLAY_OK);
            }
        } else if (job==3) {
            status=VbxeOpen(&display);
            check(status==DISPLAY_OK);
            check(VbxeClose(&display)==DISPLAY_OK);
            answer=0;
        } else {
            Forbid();
            retired++;
            Signal(parent,rootMask);
            RemTask(NULL);
        }
        Signal(parent,rootMask);
    }
}

static void send(UWORD next)
{
    job=next;
    Signal(renderer,1);
    Wait(rootMask);
}

int main(void)
{
    if (stage==0) {
        parent=FindTask(NULL);
        check(VbxeOpen(&display)==DISPLAY_BUSY);
        check(DisplayAcquire((struct DisplayLease *)0x1000000UL,DISPLAY_VBXE)==DISPLAY_INVALID_OWNER);
        check(DisplayAcquire((struct DisplayLease *)0x8000UL,DISPLAY_VBXE)==DISPLAY_INVALID_OWNER);
        rootBit=AllocSignal(-1);
        check(rootBit>=0);
        rootMask=1UL<<rootBit;
        Forbid();
        peer=CreateTask("display peer",0,Peer,2560);
        renderer=CreateTask("display owner",0,Renderer,2560);
        check(peer && renderer);
        check(RetainTask(peer,&peerLease));
        check(RetainTask(renderer,&rendererLease));
        Permit();
        Wait(rootMask);
    } else if (stage==1) {
        send(1);
        if (variant>=1 && variant<=3) {
            check(answer==DISPLAY_UNSUPPORTED);
            check(!display.mutated && display.lease.state==DISPLAY_FREE);
        } else check(answer==DISPLAY_OK);
    } else if (stage==2) {
        if (variant==7) { check(ReleaseTask(&rendererLease)); RemTask(renderer); } /* Display's retained owner blocks removal. */
        Signal(peer,1);
        job=2;
        Signal(renderer,1);
    } else if (stage==5) {
        Wait(rootMask);
    } else if (stage==3) {
        send(3);
    } else {
        if (variant>=1 && variant<=3) {
            /* This peer never borrowed graphics in negative admission cases. */
            Forbid();
            check(ReleaseTask(&peerLease));
            RemTask(peer);
            Permit();
            retired=1;
        } else {
            /* Compute finished before the second wake; wait until it has done so. */
            while (progress[0]!=30000) { /* Exec VBI remains preemptible. */ }
            Forbid();
            check(ReleaseTask(&peerLease));
            Signal(peer,1);
            Permit();
        }
        Forbid();
        check(ReleaseTask(&rendererLease));
        job=4;
        Signal(renderer,1);
        Permit();
        while (retired!=2) Wait(rootMask);
        FreeSignal(rootBit);
        finished=1;
    }
    return failures!=0;
}
