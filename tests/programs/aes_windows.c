#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure, AESReady, AESDone;
volatile UWORD AESVisibleCount, AESPhysical, AESPhysicalGo;
ULONG AESView;
WORD AESWindow, AESControl[8];
WORD AESVisible[96][4];
static struct Task *controller, *peer;
static ULONG wake, peerWake;
static volatile UWORD command, finished;
static WORD peerHandle;
static volatile UWORD extraReady, extraDone;
static ULONG extraWake[2];
static struct Task *extraTasks[2];

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure = AESChecks; }
    Permit();
}
#define CHECK(t) check((t) != 0)

void AESClientOne(void)
{
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    peerWake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    peerHandle = wind_create(NAME | CLOSER | MOVER, 89, 49, 200, 120);
    CHECK(peerHandle > 0);
    CHECK(wind_set_str(peerHandle, WF_NAME, "Occluder"));
    CHECK(wind_open(peerHandle, 89, 49, 200, 120));
    AESReady = 1;
    Signal(controller, wake);
    for (;;) {
        Wait(peerWake);
        if (command == 1) CHECK(wind_set(peerHandle, WF_CXYWH, 9, 9, 200, 120));
        else if (command == 2) CHECK(wind_close(peerHandle));
        else if (command == 3) CHECK(wind_open(peerHandle, 89, 49, 200, 120));
        else if (command == 5) CHECK(wind_set(peerHandle, WF_TOP, 0, 0, 0, 0));
        else break;
        finished = command;
        Signal(controller, wake);
    }
    /* Exit retires the still-open window and any undelivered GUI record. */
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); AESDone = 1; Signal(controller, wake); RemTask(NULL);
}
void AESClientTwo(void)
{
    WORD handle;
    UWORD who = extraReady;
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    extraWake[who] = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init() > 0);
    handle = wind_create(AES_WINDOW_KIND, 420, 130, 100, 70);
    if (who == 0) {
        CHECK(handle > 0);
        CHECK(wind_open(handle, 420, 130, 100, 70));
    } else CHECK(handle == -1 && ExecAESDiagnostic() == AES_RESOURCE);
    ++extraReady; Signal(controller, wake);
    Wait(extraWake[who]);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid(); ++extraDone; Signal(controller, wake); RemTask(NULL);
}

static void send(UWORD value)
{
    command = value;
    Signal(peer, peerWake);
    while (finished != value) Wait(wake);
}

static void geometry(WORD handle, WORD field, WORD x, WORD y, WORD w, WORD h)
{
    WORD a, b, c, d;
    CHECK(wind_get(handle, field, &a, &b, &c, &d));
    CHECK(a == x && b == y && c == w && d == h);
}

UWORD AESRun(void)
{
    WORD id, handle, replacement, a, b, c, d, message[8];
    WORD control[5] = {108, 6, 5, 0, 0}, global[15], in[6], out[5];
    AESPB pb = {control, global, in, out, NULL, NULL};
    char title[66];
    UWORD i;
    ULONG available = AvailMem(0);
    BYTE bit = AllocSignal(-1);
    CHECK(bit >= 0);
    controller = FindTask(NULL); wake = 1UL << bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id = appl_init(); CHECK(id > 0);
    CHECK(wind_calc(WC_WORK, AES_WINDOW_KIND, 9, 9, 200, 120, &a, &b, &c, &d));
    CHECK(a == 17 && b == 25 && c == 184 && d == 96);
    CHECK(wind_calc(WC_BORDER, AES_WINDOW_KIND, a, b, c, d, &a, &b, &c, &d));
    CHECK(a == 9 && b == 9 && c == 200 && d == 120);
    CHECK(!wind_calc(WC_WORK, AES_WINDOW_KIND, 0, 0, 16, 24, &a, &b, &c, &d));
    CHECK(a == 0 && b == 0 && c == 0 && d == 0);
    CHECK(!wind_calc(WC_BORDER, AES_WINDOW_KIND, -32768, 0, 20, 20, &a, &b, &c, &d));
    CHECK(!wind_calc(WC_WORK, 0, 0, 0, 200, 120, &a, &b, &c, &d));
    in[0] = WC_WORK; in[1] = AES_WINDOW_KIND;
    in[2] = 9; in[3] = 9; in[4] = 200; in[5] = 120;
    aes_call(&pb);
    CHECK(out[0] == 1 && out[1] == 17 && out[2] == 25 && out[3] == 184 && out[4] == 96);
    geometry(0, WF_WXYWH, 0, 16, 640, 224);
    CHECK(wind_create(0, 9, 9, 200, 120) == -1);
    CHECK(wind_create(AES_WINDOW_KIND, -1, 9, 200, 120) == -1);
    CHECK(wind_create(AES_WINDOW_KIND, 500, 9, 200, 120) == -1);
    handle = wind_create(AES_WINDOW_KIND, 9, 9, 200, 120); CHECK(handle > 0);
    CHECK(wind_create(AES_WINDOW_KIND, 9, 9, 200, 120) == -1);
    geometry(handle, WF_CXYWH, 9, 9, 200, 120);
    geometry(handle, WF_WXYWH, 17, 25, 184, 96);
    geometry(handle, WF_KIND, AES_WINDOW_KIND, 0, 0, 0);
    CHECK(!wind_get(handle, WF_FIRSTXYWH, &a, &b, &c, &d));
    CHECK(ExecAESDiagnostic() == AES_BUSY);
    CHECK(wind_update(BEG_UPDATE));
    geometry(handle, WF_FIRSTXYWH, 0, 0, 0, 0);
    CHECK(wind_update(END_UPDATE));
    for (i = 0; i < 65; ++i) title[i] = 'T';
    title[65] = 0;
    CHECK(!wind_set_str(handle, WF_NAME, title));
    title[64] = 0;
    CHECK(wind_set_str(handle, WF_NAME, title));
    title[0] = 'X'; /* The presenter owns a copy. */
    CHECK(!wind_open(handle, 9, 9, 201, 120));
    CHECK(wind_open(handle, 9, 9, 200, 120));
    CHECK(!wind_delete(handle));
    CHECK(!wind_open(handle, 9, 9, 200, 120));
    CHECK(!wind_set(handle, WF_CXYWH, 600, 9, 200, 120));
    geometry(handle, WF_CXYWH, 9, 9, 200, 120);
    CHECK(evnt_mesag(message));
    CHECK(message[0] == WM_REDRAW && message[3] == handle);
    CHECK(message[4] == 17 && message[5] == 25 && message[6] == 184 && message[7] == 96);
    CHECK(wind_update(BEG_UPDATE));
    geometry(handle, WF_FIRSTXYWH, 17, 25, 184, 96);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_update(END_UPDATE));
    geometry(handle, WF_NEXTXYWH, 0, 0, 0, 0);
    CHECK(wind_update(END_UPDATE));
    peer = CreateTask("AES window peer", 1, (APTR)AESClientOne, 1024UL);
    CHECK(peer != NULL);
    while (!AESReady) Wait(wake);
    /* Native shell + three GEM windows exhaust all four desktop slots. */
    for (i = 0; i < 2; ++i) {
        extraTasks[i] = CreateTask("AES capacity peer", 1, (APTR)AESClientTwo, 1024UL);
        CHECK(extraTasks[i] != NULL);
        while (extraReady < i+1) Wait(wake);
    }
    for (i = 0; i < 2; ++i) Signal(extraTasks[i], extraWake[i]);
    while (extraDone != 2) Wait(wake);
    CHECK(wind_set(handle, WF_TOP, 0, 0, 0, 0));
    /* Restore the peer above the root through its own caller. */
    command = 5; Signal(peer, peerWake);
    while (finished != 5) Wait(wake);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(0, WF_TOP, &a, &b, &c, &d) && a == peerHandle);
    AESVisibleCount = 0;
    CHECK(wind_get(handle, WF_FIRSTXYWH, &a, &b, &c, &d));
    while (c && d && AESVisibleCount < 96) {
        AESVisible[AESVisibleCount][0] = a; AESVisible[AESVisibleCount][1] = b;
        AESVisible[AESVisibleCount][2] = c; AESVisible[AESVisibleCount][3] = d;
        ++AESVisibleCount;
        CHECK(wind_get(handle, WF_NEXTXYWH, &a, &b, &c, &d));
    }
    CHECK(AESVisibleCount == 2);
    CHECK(!wind_close(peerHandle) && ExecAESDiagnostic() == AES_IDENTITY);
    finished = 0; command = 1; Signal(peer, peerWake);
    CHECK(evnt_timer(60, 0));
    CHECK(finished == 0); /* Mutation waits for the owner's update lock. */
    CHECK(wind_update(END_UPDATE));
    while (finished != 1) Wait(wake);
    CHECK(wind_update(BEG_UPDATE));
    geometry(handle, WF_FIRSTXYWH, 0, 0, 0, 0);
    CHECK(wind_update(END_UPDATE));
    send(2); send(3);
    AESView = (ULONG)ExecAESContext()->view;
    AESWindow = handle;
    for (i = 0; i < 3; ++i) {
        WORD expected = i == 0 ? WM_TOPPED : i == 1 ? WM_MOVED : WM_CLOSED;
        AESPhysical = 1 + i*2;
        do { CHECK(evnt_mesag(AESControl)); } while (AESControl[0] == WM_REDRAW);
        CHECK(AESControl[0] == expected && AESControl[3] == handle);
        AESPhysical = 2 + i*2;
        while (AESPhysicalGo != AESPhysical) ExecYield();
        if (i == 0) CHECK(wind_set(handle, WF_TOP, 0, 0, 0, 0));
        else if (i == 1) CHECK(wind_set(handle, WF_CXYWH, AESControl[4],
            AESControl[5], AESControl[6], AESControl[7]));
        else { CHECK(wind_close(handle)); CHECK(wind_open(handle, 9, 9, 200, 120)); }
    }
    AESPhysical = 7;
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(handle, WF_FIRSTXYWH, &a, &b, &c, &d));
    CHECK(wind_set(handle, WF_CXYWH, 11, 13, 200, 120));
    CHECK(!wind_get(handle, WF_NEXTXYWH, &a, &b, &c, &d));
    CHECK(ExecAESDiagnostic() == AES_BUSY);
    geometry(handle, WF_CXYWH, 11, 13, 200, 120);
    CHECK(wind_set(handle, WF_TOP, 0, 0, 0, 0));
    CHECK(wind_get(0, WF_TOP, &a, &b, &c, &d) && a == handle);
    geometry(handle, WF_FIRSTXYWH, 19, 29, 184, 96);
    CHECK(wind_update(END_UPDATE));
    command = 4; Signal(peer, peerWake);
    while (!AESDone) Wait(wake);
    /* Ordinary FIFO can be full during close/reopen; its payload is opaque. */
    for (i = 0; i < 16; ++i) { message[0] = 1000 + i; CHECK(appl_write(id, 16, message)); }
    CHECK(wind_close(handle));
    CHECK(wind_open(handle, 11, 13, 200, 120));
    for (i = 0; i < 16; ++i) { CHECK(evnt_mesag(message)); CHECK(message[0] == 1000 + i); }
    CHECK(evnt_mesag(message)); CHECK(message[0] == WM_REDRAW && message[3] == handle);
    CHECK(wind_close(handle));
    CHECK(wind_delete(handle));
    CHECK(!wind_get(handle, WF_CXYWH, &a, &b, &c, &d));
    replacement = wind_create(AES_WINDOW_KIND, 9, 9, 200, 120);
    CHECK(replacement > handle);
    CHECK(wind_open(replacement, 9, 9, 200, 120));
    CHECK(wind_close(replacement));
    CHECK(wind_delete(replacement));
    /* The application accepts geometry and owns logical slider values. */
    handle=wind_create(AES_WINDOW_KIND|SIZER|UPARROW|DNARROW|VSLIDE,32,32,240,160);
    CHECK(handle>0);
    CHECK(wind_open(handle,32,32,240,160));
    geometry(handle,WF_WXYWH,40,48,216,128);
    geometry(handle,WF_VSLIDE,0,0,0,0);
    geometry(handle,WF_VSLSIZE,1000,0,0,0);
    CHECK(wind_calc(WC_WORK,AES_WINDOW_KIND|SIZER|UPARROW|DNARROW|VSLIDE,
        32,32,240,160,&a,&b,&c,&d));
    CHECK(a==40 && b==48 && c==216 && d==128);
    CHECK(wind_calc(WC_BORDER,AES_WINDOW_KIND|SIZER|UPARROW|DNARROW|VSLIDE,
        a,b,c,d,&a,&b,&c,&d));
    CHECK(a==32 && b==32 && c==240 && d==160);
    CHECK(wind_set(handle,WF_VSLSIZE,250,0,0,0));
    CHECK(wind_set(handle,WF_VSLIDE,1000,0,0,0));
    geometry(handle,WF_VSLSIZE,250,0,0,0);
    geometry(handle,WF_VSLIDE,1000,0,0,0);
    CHECK(!wind_set(handle,WF_VSLIDE,1001,0,0,0));
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(handle,WF_FIRSTXYWH,&a,&b,&c,&d));
    CHECK(wind_set(handle,WF_CXYWH,32,32,320,192));
    CHECK(!wind_get(handle,WF_NEXTXYWH,&a,&b,&c,&d));
    geometry(handle,WF_WXYWH,40,48,296,160);
    geometry(handle,WF_FIRSTXYWH,40,48,296,160);
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_set(handle,WF_CXYWH,32,32,64,80));
    geometry(handle,WF_WXYWH,40,48,40,48);
    CHECK(!wind_set(handle,WF_CXYWH,32,32,63,80));
    CHECK(!wind_set(handle,WF_CXYWH,32,32,64,79));
    CHECK(wind_close(handle));
    CHECK(wind_open(handle,32,32,240,160));
    geometry(handle,WF_WXYWH,40,48,216,128);
    AESView=(ULONG)ExecAESContext()->view;
    AESWindow=handle;
    for (i=0;i<7;++i) {
        AESPhysical=10+i*2;
        do { CHECK(evnt_mesag(AESControl)); } while (AESControl[0]==WM_REDRAW);
        CHECK(AESControl[3]==handle);
        CHECK(AESControl[0]==(i==0 ? WM_SIZED:(i==4 || i==6 ? WM_VSLID:WM_ARROWED)));
        AESPhysical=11+i*2;
        while (AESPhysicalGo!=AESPhysical) ExecYield();
        if (!i) CHECK(wind_set(handle,WF_CXYWH,AESControl[4],AESControl[5],AESControl[6],AESControl[7]));
        else if (i==4 || i==6) CHECK(wind_set(handle,WF_VSLIDE,AESControl[4],0,0,0));
    }
    AESPhysical=24;
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    CHECK(AvailMem(0) == available);
    return AESFailures;
}
