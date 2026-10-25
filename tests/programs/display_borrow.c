#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <exec/display.h>
#include <clib/alib_protos.h>
#include "gem-drawing.h"

extern UWORD GemBitmapFill(UWORD,UWORD,UWORD,UWORD,UWORD);
extern volatile UWORD ConsoleFaultMode;
ULONG AESService, DisplayAdmission, DisplayController, DisplayWake;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
volatile UWORD DisplayCommand, DisplayStatus, DisplayPhase, DisplayGo;
volatile UWORD DisplayActive, DisplayBorrows, DisplayNative, DisplayOverlap, DisplayCopies;
volatile UWORD DisplayIterations[2];
volatile UWORD DisplayFaultVariant;
volatile UWORD DisplayCopyProbe,DisplayCopySteps;
static struct VbxeCopy copy;
static UBYTE copyEdges[480];
static struct DisplayGrant grants[2];
static struct Task *peers[2];
static volatile UWORD released;
static char text[512];

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)

/* Called by the instrumented adapter only after admission, before its first
 * scratch/overlay access, and after the last fence, before relinquishing it. */
void DisplayBorrowBegin(struct DisplayGrant *g)
{
    if (DisplayActive) ++DisplayOverlap;
    DisplayActive = g->slot+1;
    ++DisplayBorrows;
}
void DisplayBorrowEnd(struct DisplayGrant *g)
{
    if (DisplayActive != g->slot+1) ++DisplayOverlap;
    DisplayActive = 0;
}
void DisplayNativeBegin(void)
{
    if (DisplayActive) ++DisplayOverlap;
    ++DisplayNative;
}

void DisplayDMAStart(void)
{
    if (DisplayGo == 1 && released < 2) ++DisplayCopies;
}

/* Inject BUSY only after one real screen strip has completed. The next fence
 * must recover an operational error after mutation, retaining unsafe access
 * until quiescence or reset. This is a test hook, outside production sources. */
void DisplayCopyStep(void)
{
    if (DisplayCopyProbe && !DisplayCopySteps++)
        ConsoleFaultMode=DisplayFaultVariant;
}

static void paint(void *context)
{
    UWORD who = *(UWORD *)context;
    UWORD x = 563+who*40;
    if (DisplayFaultVariant) ConsoleFaultMode=DisplayFaultVariant;
    CHECK(GemBitmapFill(x,181,x+34,213,who ? 2 : 4) == 0);
    CHECK(FindTask(NULL)->tc_TDNestCnt == (DisplayIterations[who] == 0 ? 0 : -1));
    /* Inject a switch with renderer staging live and no inherited Forbid.
     * Production callbacks never yield or wait. Ownership must survive. */
    if (DisplayIterations[who] == 1) ExecYield();
    CHECK(DisplayActive == grants[who].slot+1);
}

static void worker(UWORD who)
{
    BYTE bit = AllocSignal(-1);
    UWORD i;
    CHECK(bit >= 0);
    grants[who].task = FindTask(NULL);
    grants[who].mask = 1UL << bit;
    Forbid(); ++AESReady; Signal((struct Task *)DisplayController,DisplayWake); Permit();
    while (!DisplayGo) Wait(grants[who].mask);
    for (i = 0; i < (DisplayFaultVariant ? 1 : 24); ++i) {
        UWORD status;
        BYTE nesting;
        /* Exercise inherited exclusion too, including queued admission. */
        if (i == 0) Forbid();
        nesting = FindTask(NULL)->tc_TDNestCnt;
        if (!who) {
            if (DisplayCopyProbe) {
                copy.source.offset=copy.destination.offset=0;
                copy.source.pitch=copy.destination.pitch=320;
                copy.source.width=copy.destination.width=640;
                copy.source.height=copy.destination.height=240;
                copy.sourceX=563; copy.sourceY=181;
                copy.destinationX=565; copy.destinationY=183;
                copy.width=33; copy.height=48;
                status=GemDrawingCopyBorrow(&grants[who],&copy,copyEdges);
            } else {
                if (DisplayFaultVariant) ConsoleFaultMode=DisplayFaultVariant;
                status=GemDrawingSolidBorrow(&grants[who],563,181,597,231,4);
            }
        } else status=GemDrawingBorrow(&grants[who],603,181,637,213,paint,&who);
        CHECK(status==(DisplayFaultVariant ? DISPLAY_DEVICE_FAULT : DISPLAY_OK));
        CHECK(FindTask(NULL)->tc_TDNestCnt == nesting);
        if (i == 0) Permit();
        ++DisplayIterations[who];
    }
    SetSignal(0,grants[who].mask);
    Forbid(); ++released; Signal((struct Task *)DisplayController,DisplayWake); Permit();
    /* Keep the grant live for the host's pixel and teardown observations. */
    do { Wait(grants[who].mask); } while (DisplayGo != 2);
    CHECK(DisplayGrantClose(&grants[who]) == DISPLAY_OK);
    CHECK(GemDrawingSolidBorrow(&grants[who],563,181,597,213,4) != DISPLAY_OK);
    CHECK(FindTask(NULL)->tc_TDNestCnt == -1);
    FreeSignal(bit);
    Forbid(); ++AESDone; Signal((struct Task *)DisplayController,DisplayWake); RemTask(NULL);
}
void AESClientOne(void) { worker(0); }
void AESClientTwo(void) { worker(1); }

static void admit(UWORD who)
{
    struct ExecAESContext *c = ExecAESContext();
    DisplayAdmission = (ULONG)&grants[who];
    DisplayCommand = 1;
    Signal(c->directory->owner,c->directory->mask);
    while (DisplayCommand) Wait(DisplayWake);
    CHECK(DisplayStatus == DISPLAY_OK);
}

UWORD AESRun(void)
{
    struct MsgPort *port;
    struct IOStdReq *request;
    BYTE bit = AllocSignal(-1);
    UWORD i;
    ULONG available;
    CHECK(bit >= 0);
    DisplayWake = 1UL << bit;
    DisplayController = (ULONG)FindTask(NULL);
    available = AvailMem(0);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    port = CreateMsgPort(); CHECK(port != NULL);
    request = (struct IOStdReq *)CreateIORequest(port,sizeof(*request)); CHECK(request != NULL);
    CHECK(OpenDevice("console.device",0,(struct IORequest *)request,0) == 0);
    for (i = 0; i < 512; ++i) text[i] = i%64 == 63 ? '\n' : 'A'+i%26;
    request->io_Command = CMD_WRITE;
    request->io_Data = text; request->io_Length = 512;
    for (i = 0; i < 3; ++i) CHECK(DoIO((struct IORequest *)request) == 0);
    peers[0] = CreateTask("display borrower A",1,(APTR)AESClientOne,1024UL);
    peers[1] = CreateTask("display borrower B",1,(APTR)AESClientTwo,1024UL);
    CHECK(peers[0] != NULL && peers[1] != NULL);
    while (AESReady != 2) Wait(DisplayWake);
    admit(0); admit(1);
    CHECK(DisplayDelegated() == 2);
    DisplayPhase = 1;
    while (!DisplayGo) ExecYield();
    request->io_Command = CMD_WRITE;
    request->io_Data = text; request->io_Length = 512;
    if (!DisplayFaultVariant) SendIO((struct IORequest *)request);
    Signal(peers[0],grants[0].mask); Signal(peers[1],grants[1].mask);
    while (released != 2) Wait(DisplayWake);
    if (!DisplayFaultVariant) {
        CHECK(WaitIO((struct IORequest *)request) == 0 && request->io_Actual == 512);
        CHECK(DisplayIterations[0] == 24 && DisplayIterations[1] == 24);
        CHECK(DisplayBorrows == 48 && DisplayNative > 0 && DisplayCopies > 0);
    } else {
        CHECK(DisplayIterations[0] == 1 && DisplayIterations[1] == 1);
        CHECK(grants[0].state == DISPLAY_GRANT_REVOKED && grants[1].state == DISPLAY_GRANT_REVOKED);
    }
    CHECK(DisplayOverlap == 0 && DisplayActive == 0);
    DisplayPhase = 2;
    while (DisplayGo != 2) ExecYield();
    Signal(peers[0],grants[0].mask); Signal(peers[1],grants[1].mask);
    while (AESDone != 2) Wait(DisplayWake);
    CHECK(DisplayDelegated() == 0);
    CloseDevice((struct IORequest *)request); DeleteIORequest((struct IORequest *)request); DeleteMsgPort(port);
    CHECK(ExecAESDetach());
    CHECK(AvailMem(0) == available);
    FreeSignal(bit);
    return AESFailures;
}
