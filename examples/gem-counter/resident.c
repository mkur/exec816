/* SPDX-License-Identifier: MIT */
#include "counter.h"
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <string.h>

ULONG GEMCountersService;
struct Counter GEMCounters[2];
volatile UWORD GEMCountersDone,GEMCountersFailure;
static const struct CounterConfig config[2]={
    {"Counter A",65,49,208,104,4,0},
    {"Counter B",241,97,208,104,2,0}
};
static struct Task *controller,*workers[2];
static BYTE bit=-1;
static ULONG wake;
static UWORD stopping[2];

static void run(UWORD who)
{
    UWORD result=1;
    if (ExecAESAttach((struct MsgPort *)GEMCountersService)) {
        result=CounterRun(&GEMCounters[who]);
        /* A failed detach leaves the Task and image retained. The controller
         * reports the failure; it cannot free a live registration. */
        if (!ExecAESDetach()) {
            GEMCountersFailure=3; Signal(controller,wake);
            for (;;) Wait(0);
        }
    }
    Forbid();
    if (result) GEMCountersFailure=result;
    workers[who]=NULL; ++GEMCountersDone;
    Signal(controller,wake);
    RemTask(NULL);
}
void GEMCounterOne(void) { run(0); }
void GEMCounterTwo(void) { run(1); }

UWORD GEMCountersStop(void)
{
    WORD message[8]={WM_CLOSED,0,0,0,0,0,0,0};
    UWORD i,live;
    if (bit<0) return 1;
    do {
        live=0;
        for (i=0;i<2;++i) if (workers[i]) {
            ++live;
            if (!stopping[i] && GEMCounters[i].ready) {
                message[3]=GEMCounters[i].window;
                if (appl_write(GEMCounters[i].id,16,message)) stopping[i]=1;
            }
        }
        if (GEMCountersFailure==3) return 0;
        if (live) ExecYield();
    } while (live);
    if (!ExecAESDetach()) return 0;
    FreeSignal(bit); bit=-1;
    return 1;
}

UWORD GEMCountersStart(void)
{
    UWORD i;
    if (bit>=0) return 0;
    controller=FindTask(NULL); bit=AllocSignal(-1);
    if (bit<0) return 0;
    wake=1UL<<bit;
    GEMCountersDone=GEMCountersFailure=0;
    memset(GEMCounters,0,sizeof(GEMCounters));
    for (i=0;i<2;++i) { GEMCounters[i].config=&config[i]; stopping[i]=0; }
    if (!ExecAESAttach((struct MsgPort *)GEMCountersService) || appl_init()<0) {
        GEMCountersStop(); return 0;
    }
    /* Publish Task pointers before a worker can retire after failed startup. */
    Forbid();
    workers[0]=CreateTask("GEM Counter A",1,(APTR)GEMCounterOne,1024UL);
    workers[1]=CreateTask("GEM Counter B",1,(APTR)GEMCounterTwo,1024UL);
    Permit();
    if (!workers[0] || !workers[1]) { GEMCountersStop(); return 0; }
    while ((!GEMCounters[0].ready || !GEMCounters[1].ready) && !GEMCountersFailure) ExecYield();
    if (GEMCountersFailure) { GEMCountersStop(); return 0; }
    return 1;
}
