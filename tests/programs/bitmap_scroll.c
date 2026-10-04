/* Emitted async contract: real BUSY, retained records, exact pixels and faults. */
#include <hardware/vbxe.h>
#include <proto/exec.h>
#include <string.h>
extern struct VbxeDisplay display;
extern volatile UWORD variant,ownerChecks,fault_arm,ProbeStopped;
extern volatile ULONG tickAddress;
volatile UWORD scrollChecks,scrollFailures,scrollFirstFailure,scrollLaunches;
volatile UWORD scrollBusySeen,scrollPolls;
volatile ULONG notifyControl;
static UBYTE row[320];
static struct VbxeCopy copy;

void ProbeScrollLaunch(void) { ++scrollLaunches; }
static void check(UWORD good)
{
    ++scrollChecks;
    if (!good) { if (!scrollFailures) scrollFirstFailure=scrollChecks; ++scrollFailures; }
}
static void geometry(UWORD x,UWORD y,UWORD width,UWORD rows)
{
    memset(&copy,0,sizeof(copy));
    copy.source.pitch=copy.destination.pitch=320;
    copy.source.width=copy.destination.width=640;
    copy.source.height=copy.destination.height=240;
    copy.sourceX=copy.destinationX=x;
    copy.sourceY=y+8; copy.destinationY=y;
    copy.width=width; copy.height=rows;
}
/* Recreate the source independently for each delta. Read the whole screen so
 * a correct tile cannot hide damage to neighbouring rows or columns. */
static void multirow(UWORD left,UWORD top,UWORD width,UWORD height,UWORD delta)
{
    ULONG id=0;
    UWORD x,y,good,expected,launches;
    for (y=0;y<240;y++) {
        memset(row,(UBYTE)y,sizeof(row));
        check(VbxeWrite(&display,(ULONG)y*320,row,sizeof(row))==DISPLAY_OK);
    }
    geometry(left,top,width,height-delta);
    copy.sourceY=top+delta;
    launches=scrollLaunches;
    check(VbxeScrollStart(&display,&copy,0xe5,&id)==DISPLAY_OK);
    check(scrollLaunches==launches+1 && id!=0);
    check(VbxeFence(&display)==DISPLAY_OK);
    check(VbxeScrollPoll(&display,id)==DISPLAY_OK);
    check(!(*(volatile UBYTE *)0xd65eUL));
    for (y=0;y<240;y++) {
        check(VbxeRead(&display,(ULONG)y*320,row,sizeof(row))==DISPLAY_OK);
        good=1;
        for (x=0;x<320;x++) {
            expected=y;
            if (x>=left/2 && x<(left+width)/2 && y>=top && y<top+height)
                expected=y<top+height-delta ? y+delta : 0xe5;
            if (row[x]!=expected) good=0;
        }
        check(good);
    }
}
void ScrollCases(void)
{
    ULONG id=0,old,rejected=0x12345678UL,completion;
    UWORD x,y,before,launches,status,started,good;
    completion=VbxeCompletionMask(&display);
    check(completion!=0);
    geometry(0,0,640,232);
    check(VbxeScrollStart(&display,NULL,0,&id)==DISPLAY_BAD_ARGUMENT);
    check(VbxeScrollStart(&display,&copy,0,NULL)==DISPLAY_BAD_ARGUMENT);
    check(VbxeScrollStart(&display,&copy,0,(ULONG *)0x8000UL)==DISPLAY_BAD_ARGUMENT);
    copy.sourceX=1;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    copy.sourceX=0; copy.height=233;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    geometry(0,0,640,0);
    copy.sourceY=0;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    copy.sourceY=9;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    copy.sourceY=0xffff;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    copy.sourceY=8; copy.destinationY=16;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    copy.destinationY=0; copy.sourceY=240; copy.height=1;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    geometry(0,0,639,208); copy.sourceY=32;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_BAD_ARGUMENT);
    check(id==0);
    geometry(0,0,640,232);
    for (y=0;y<240;y++) {
        memset(row,(UBYTE)y,sizeof(row));
        check(VbxeWrite(&display,(ULONG)y*320,row,sizeof(row))==DISPLAY_OK);
    }
    if (variant==14 || variant==16) *(volatile UWORD *)tickAddress=0xfffe;
    started=DisplayTicks();
    launches=scrollLaunches; before=ownerChecks;
    check(VbxeScrollStart(&display,&copy,0xa5,&id)==DISPLAY_OK);
    check((UWORD)(ownerChecks-before)==1 && id!=0);
    check((UWORD)(scrollLaunches-launches)==1);
    check(display.scrollPending && (*(volatile UBYTE *)0xd653UL&3));
    scrollBusySeen=1;
    check(VbxeScrollStart(&display,&copy,0,&rejected)==DISPLAY_BUSY);
    check(rejected==0x12345678UL && scrollLaunches==launches+1);
    check(VbxeScrollPoll(&display,id+1)==DISPLAY_BAD_ARGUMENT);
    /* The completed launch owns its records; the original descriptor can die. */
    memset(&copy,0xcc,sizeof(copy));
    if (variant>=13 && variant<=15) { fault_arm=1; ProbeStopped=0; }
    if (variant==16) {
        /* Lost source delivery: retain the actual ARMED mailbox and timer.
         * The list completes normally, but only its independent timeout wakes. */
        *(volatile UBYTE *)0xd654UL=0;
        *(volatile UBYTE *)notifyControl=0;
    }
    if (variant==12 || variant==16) check((Wait(completion)&completion)!=0);
    if (variant==16) {
        check(*(volatile UBYTE *)(notifyControl-13)==3);
        check((UWORD)(DisplayTicks()-started)>=15 && DisplayTicks()<32);
    }
    do {
        before=ownerChecks;
        status=VbxeScrollPoll(&display,id);
        check((UWORD)(ownerChecks-before)==1);
        ++scrollPolls;
    } while (status==DISPLAY_BUSY);
    if (variant>=13 && variant<=15) {
        check(status==DISPLAY_DEVICE_FAULT && !display.scrollPending);
        check(display.lease.state==DISPLAY_FREE && ProbeStopped);
        /* DONE with injected BUSY is an immediate contradiction, not a
         * missing IRQ. Independent lost-IRQ/tick-wrap coverage waits in the
         * native blitter fixture with only the watchdog timer running. */
        check((UWORD)(DisplayTicks()-started)<VBXE_WAIT_TICKS+2);
        fault_arm=0;
        check(VbxeOpen(&display)==DISPLAY_OK);
        check(VbxeScrollPoll(&display,id)==DISPLAY_BAD_ARGUMENT);
        geometry(0,0,640,232);
        launches=scrollLaunches; rejected=0x12345678UL;
        fault_arm=1; ProbeStopped=0;
        check(VbxeScrollStart(&display,&copy,0,&rejected)==DISPLAY_DEVICE_FAULT);
        check(rejected==0x12345678UL && scrollLaunches==launches);
        check(display.lease.state==DISPLAY_FREE && !display.scrollPending);
        fault_arm=0;
        check(VbxeOpen(&display)==DISPLAY_OK);
        return;
    }
    check(status==DISPLAY_OK && !display.scrollPending);
    check(VbxeScrollPoll(&display,id)==DISPLAY_OK);
    for (y=0;y<240;y++) {
        check(VbxeRead(&display,(ULONG)y*320,row,sizeof(row))==DISPLAY_OK);
        good=1;
        for (x=0;x<320;x++) if (row[x]!=(y<232 ? (UBYTE)(y+8) : 0xa5)) good=0;
        check(good);
    }
    /* Narrow offset tile and height-one fill preserve every neighbouring byte. */
    check(VbxeFill(&display,0,320,320,240,0x11)==DISPLAY_OK);
    check(VbxeFill(&display,24UL*320+12,320,68,16,0x33)==DISPLAY_OK);
    geometry(24,16,136,16); old=id;
    check(VbxeScrollStart(&display,&copy,0x77,&id)==DISPLAY_OK && id!=old);
    check(VbxeScrollPoll(&display,old)==DISPLAY_BAD_ARGUMENT);
    check(VbxeFence(&display)==DISPLAY_OK && !display.scrollPending);
    geometry(200,80,16,0);
    check(VbxeScrollStart(&display,&copy,0x99,&id)==DISPLAY_OK);
    /* A normal synchronous operation drains the async list before reuse. */
    check(VbxeFill(&display,0,320,1,1,0x11)==DISPLAY_OK);
    check(VbxeScrollPoll(&display,id)==DISPLAY_OK);
    for (y=0;y<240;y++) {
        check(VbxeRead(&display,(ULONG)y*320,row,sizeof(row))==DISPLAY_OK);
        good=1;
        for (x=0;x<320;x++) {
            UWORD expected=0x11;
            if (x>=12 && x<80 && y>=16 && y<40) expected=y<32 ? 0x33 : 0x77;
            if (x>=100 && x<108 && y>=80 && y<88) expected=0x99;
            if (row[x]!=expected) good=0;
        }
        check(good);
    }
    multirow(24,16,136,112,16);
    multirow(0,0,640,240,32);
    multirow(0,0,640,240,232);
    multirow(0,0,640,240,240);
    geometry(0,0,640,232); old=id;
    check(VbxeScrollStart(&display,&copy,0,&id)==DISPLAY_OK);
    check(VbxeClose(&display)==DISPLAY_OK && !display.scrollPending);
    check(VbxeOpen(&display)==DISPLAY_OK);
    check(VbxeScrollPoll(&display,id)==DISPLAY_BAD_ARGUMENT);
    check(VbxeScrollStart(&display,&copy,0,&old)==DISPLAY_OK && old!=id);
    check(VbxeFence(&display)==DISPLAY_OK);
}
