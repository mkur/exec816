/* G5: real VDI, a non-yielding C peer, and an Action-side cold physical read.
 * Only diagnostic builds contain rendezvous/status substitution/readback hooks. */
#include "gem-vbxe.h"
#include <hardware/vbxe.h>
#include <clib/alib_protos.h>
#include <string.h>

volatile UWORD stage, variant, checks, failures, first_failure, finished;
volatile UWORD progress[2], gate, entered, commandCount, inject, stopped, completed, retired;
volatile UWORD startTick, endTick, crossings;
volatile ULONG checksum, pixelHash;
struct GemServer server;
struct GemClient client;
static struct Task *parent, *peer;
static struct TaskLease peerLease;
static void *held[32];
static ULONG sizes[32];
static UWORD heldCount;
static volatile UWORD blockerDone;

void Blocker(void)
{
    Wait(1);
    Forbid();
    blockerDone=1;
    Signal(parent,1UL<<30);
    RemTask(NULL);
}

static void check(UWORD good)
{
    ++checks;
    if (!good) { if (!failures) first_failure=checks; ++failures; }
}
void Peer(void)
{
    ULONG a=0x12345678UL,b=0x87654321UL;
    UWORD i;
    Wait(1);
    for (i=0;i<30000;i++) {
        a=((a<<1)^(a>>31))^b;
        b+=a^i;
        progress[0]=i+1;
    }
    checksum=a^b;
    Wait(1);
    Forbid();
    retired=1;
    Signal(parent,1UL<<30);
    RemTask(NULL);
}
#ifdef GEM_DIAGNOSTIC
UBYTE ProbeBusy(void)
{
    if (inject && (variant==4 || !stopped)) return 2;
    return *(volatile UBYTE *)0xd653UL;
}
void ProbeDraw(void) { ++progress[1]; }
void ProbeCommand(void)
{
    ++commandCount;
    if (!entered) {
        entered=1;
        if (variant==2) {
            Signal(parent,1UL<<29);
            while (server.state==GEM_RUNNING) { }
        } else if (!variant) {
            while (!*(volatile UWORD *)0x6000UL) { }
        }
        if (variant==3 || variant==4) inject=1;
    }
}
void ProbeSnapshot(struct VbxeDisplay *display)
{
    UBYTE row[320];
    UWORD y,x;
    ULONG hash=2166136261UL;
    if (commandCount!=12 || pixelHash || inject) return;
    for (y=0;y<240;y++) {
        check(VbxeRead(display,(ULONG)y*320,row,320)==DISPLAY_OK);
        for (x=0;x<320;x++) hash=(hash^row[x])*16777619UL;
    }
    pixelHash=hash;
}
#endif
static void exhaust(ULONG spare)
{
    ULONG bytes;
    void *reserve=spare ? AllocMem(spare,MEMF_PUBLIC) : NULL;
    while ((bytes=AvailMem(MEMF_LARGEST))!=0 && heldCount<32) {
        sizes[heldCount]=bytes;
        held[heldCount]=AllocMem(bytes,MEMF_PUBLIC);
        check(held[heldCount]!=NULL);
        ++heldCount;
    }
    check(AvailMem(0)==0);
    if (reserve) FreeMem(reserve,spare);
}
static void restore(void)
{
    while (heldCount) { --heldCount; FreeMem(held[heldCount],sizes[heldCount]); }
}
static void batch(void)
{
    struct GemCommand *c;
    WORD *values;
    UWORD i,j,offset=GEM_REQUEST_BYTES+12*GEM_COMMAND_BYTES;
    check(GemPrepare(&client,GEM_OP_SUBMIT,12,12*(GEM_COMMAND_BYTES+132))==GEM_OK);
    c=(struct GemCommand *)(client.packet+1);
    for (i=0;i<12;i++) {
        values=(WORD *)((UBYTE *)client.packet+offset);
        values[0]=64; values[1]=24+i*16;
        for (j=0;j<64;j++) values[j+2]=32+(i*64+j)%96;
        c[i].opcode=8; c[i].point_pairs=1; c[i].int_words=64;
        c[i].points_offset=offset; c[i].ints_offset=offset+4;
        offset+=132;
    }
}
UWORD main(void)
{
    UWORD status,count=0;
    BYTE bits[16],bit;
    struct Task *blocker=NULL;
    if (stage==0) {
        parent=FindTask(NULL);
        check(AllocSignal(29)==29 && AllocSignal(30)==30);
        Forbid();
        peer=CreateTask("GEM compute",0,(APTR)Peer,2560UL);
        check(peer!=NULL && RetainTask(peer,&peerLease));
        Permit();
        if (variant==11) {
            blocker=CreateTask("large pool holder",0,(APTR)Blocker,2560UL);
            check(blocker!=NULL);
        }
        if (variant==12) while ((bit=AllocSignal(-1))!=-1) bits[count++]=bit;
        if (variant==5 || variant==6) exhaust(variant==6 ? 224 : 192);
        if (variant==9 || variant==10) exhaust(variant==10 ? 32 : 0);
        status=GemServiceStart(&server,&GemVbxeBackend);
        if (variant==5 || variant==6 || variant==9 || variant==10 || variant==11 || variant==12) {
            check(status==GEM_NO_MEMORY && !server.worker && !server.port && !server.scratch);
            check(!server.owner_lease.task && !server.worker_lease.task);
            check(!server.stop_packet && !server.stop_replies);
            restore();
            if (variant==11) {
                Signal(blocker,1);
                while (!blockerDone) Wait(1UL<<30);
            }
            if (variant==12) while (count) FreeSignal(bits[--count]);
            memset(&server,0,sizeof(server));
            status=GemServiceStart(&server,&GemVbxeBackend);
        }
        check(status==GEM_OK);
        if (variant==7 || variant==8) exhaust(variant==8 ? 32 : 0);
        status=GemClientInit(&client,&server);
        if (variant==7 || variant==8) {
            check(status==GEM_NO_MEMORY && !server.client);
            restore();
            status=GemClientInit(&client,&server);
        }
        check(status==GEM_OK);
    } else if (stage==1) {
        check(GemOpen(&client)==GEM_OK); ++crossings;
        check(GemClose(&client)==GEM_OK); ++crossings;
        check(GemOpen(&client)==GEM_OK); ++crossings;
    } else if (stage==2) {
        batch();
        startTick=DisplayTicks();
        Signal(peer,1);
        if (variant==1) Forbid();
        check(GemSubmit(&client)==GEM_OK); ++crossings;
        check(client.pending==client.packet && GemClientDispose(&client)==GEM_BUSY);
        if (variant==1 || variant==2) {
            if (variant==2) while (!entered) Wait(1UL<<29);
            check(GemServiceStop(&server)==GEM_OK); ++crossings;
            if (variant==1) Permit();
            check(client.pending==client.packet && GemClientDispose(&client)==GEM_BUSY);
        }
    } else if (stage==3) {
        status=GemCollect(&client);
        endTick=DisplayTicks();
#ifndef GEM_DIAGNOSTIC
        /* Give the optional artifact a visible, bounded three-second scene. */
        while ((UWORD)(DisplayTicks()-endTick)<150) { }
#endif
        check(status==(variant==3 ? GEM_DEVICE_FAULT : GEM_OK));
        completed=client.packet->completed_count;
        check(completed==(variant==3 ? 0 : 12));
        check(!client.pending && !server.inflight);
        if (variant!=1 && variant!=2) {
            if (variant==3) {
                inject=0; stopped=0;
                check(!client.session && !server.session);
                check(GemOpen(&client)==GEM_OK); ++crossings;
            }
            if (variant==13) {
                exhaust(0);
                check(GemServiceStop(&server)==GEM_OK); ++crossings;
                restore();
            } else {
                check(GemClose(&client)==GEM_OK); ++crossings;
                check(GemServiceStop(&server)==GEM_OK); ++crossings;
            }
        }
        check(GemClientDispose(&client)==GEM_OK);
        check(!server.port && !server.scratch && !server.worker);
        check(!server.owner_lease.task && !server.worker_lease.task);
        check(!server.stop_packet && !server.stop_replies);
    } else {
        while (progress[0]!=30000) { }
        Forbid();
        check(ReleaseTask(&peerLease));
        Signal(peer,1);
        Permit();
        while (!retired) Wait(1UL<<30);
        FreeSignal(29); FreeSignal(30);

        finished=1;
    }
    return failures;
}
