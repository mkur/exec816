/* SPDX-License-Identifier: MIT */
#include "panel.h"
#include "../gem-counter/counter.h"
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <string.h>

ULONG GEMDesktopService;
struct Panel GEMPanel;
struct Counter GEMCounter;
volatile UWORD GEMDesktopDone,GEMDesktopFailure;
static const struct CounterConfig config={"Counter",192,32,208,104,4,0};
static struct Task *controller,*workers[2];
static BYTE bit=-1;
static ULONG wake;
static UWORD stopping[2];

static void run(UWORD who)
{
    UWORD result=1;
    if (ExecAESAttach((struct MsgPort *)GEMDesktopService)) {
        result=who ? CounterRun(&GEMCounter):PanelRun(&GEMPanel);
        /* A failed detach leaves the Task and image retained. The controller
         * reports the failure; it cannot free a live registration. */
        if (!ExecAESDetach()) {
            GEMDesktopFailure=3; Signal(controller,wake);
            for (;;) Wait(0);
        }
    }
    Forbid();
    if (result) GEMDesktopFailure=result;
    workers[who]=NULL; ++GEMDesktopDone;
    Signal(controller,wake);
    RemTask(NULL);
}
void GEMPanelTask(void) { run(0); }
void GEMCounterTask(void) { run(1); }

UWORD GEMDesktopStop(void)
{
    WORD message[8]={WM_CLOSED,0,0,0,0,0,0,0};
    UWORD i,live;
    if (bit<0) return 1;
    do {
        live=0;
        for (i=0;i<2;++i) if (workers[i]) {
            ++live;
            if (!stopping[i] && (i ? GEMCounter.ready:GEMPanel.ready)) {
                message[3]=(i ? GEMCounter.window:GEMPanel.window);
                if (appl_write((i ? GEMCounter.id:GEMPanel.id),16,message)) stopping[i]=1;
            }
        }
        if (GEMDesktopFailure==3) return 0;
        if (live) ExecYield();
    } while (live);
    if (!ExecAESDetach()) return 0;
    FreeSignal(bit); bit=-1;
    return 1;
}

UWORD GEMDesktopStart(void)
{
    UWORD i;
    if (bit>=0) return 0;
    controller=FindTask(NULL); bit=AllocSignal(-1);
    if (bit<0) return 0;
    wake=1UL<<bit;
    GEMDesktopDone=GEMDesktopFailure=0;
    memset(&GEMPanel,0,sizeof(GEMPanel));
    memset(&GEMCounter,0,sizeof(GEMCounter));
    GEMCounter.config=&config;
    for (i=0;i<2;++i) stopping[i]=0;
    if (!ExecAESAttach((struct MsgPort *)GEMDesktopService) || appl_init()<0) {
        GEMDesktopStop(); return 0;
    }
    /* Publish Task pointers before a worker can retire after failed startup. */
    Forbid();
    workers[0]=CreateTask("GEM Control Panel",1,(APTR)GEMPanelTask,1024UL);
    workers[1]=CreateTask("GEM Counter",1,(APTR)GEMCounterTask,1024UL);
    Permit();
    if (!workers[0] || !workers[1]) { GEMDesktopStop(); return 0; }
    while ((!GEMPanel.ready || !GEMCounter.ready) && !GEMDesktopFailure) ExecYield();
    if (GEMDesktopFailure) { GEMDesktopStop(); return 0; }
    return 1;
}
