/* SPDX-License-Identifier: MIT */
#include "input.h"
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <string.h>

ULONG GEMInputsService;
struct InputApp GEMInputs[2];
volatile UWORD GEMInputsDone,GEMInputsFailure;
static const struct InputConfig config[2]={
    {"Input A",65,49,224,128,4,0},
    {"Input B",273,97,224,128,2,0}
};
static struct Task *controller,*workers[2];
static BYTE bit=-1;
static ULONG wake;
static UWORD stopping[2];

static void run(UWORD who)
{
    UWORD result=1;
    if (ExecAESAttach((struct MsgPort *)GEMInputsService)) {
        result=InputRun(&GEMInputs[who]);
        /* A failed detach leaves the Task and image retained. The controller
         * reports the failure; it cannot free a live registration. */
        if (!ExecAESDetach()) {
            GEMInputsFailure=3; Signal(controller,wake);
            for (;;) Wait(0);
        }
    }
    Forbid();
    if (result) GEMInputsFailure=result;
    workers[who]=NULL; ++GEMInputsDone;
    Signal(controller,wake);
    RemTask(NULL);
}
void GEMInputOne(void) { run(0); }
void GEMInputTwo(void) { run(1); }

UWORD GEMInputsStop(void)
{
    WORD message[8]={WM_CLOSED,0,0,0,0,0,0,0};
    UWORD i,live;
    if (bit<0) return 1;
    do {
        live=0;
        for (i=0;i<2;++i) if (workers[i]) {
            ++live;
            if (!stopping[i] && GEMInputs[i].ready) {
                message[3]=GEMInputs[i].window;
                if (appl_write(GEMInputs[i].id,16,message)) stopping[i]=1;
            }
        }
        if (GEMInputsFailure==3) return 0;
        if (live) ExecYield();
    } while (live);
    if (!ExecAESDetach()) return 0;
    FreeSignal(bit); bit=-1;
    return 1;
}

UWORD GEMInputsStart(void)
{
    UWORD i;
    if (bit>=0) return 0;
    controller=FindTask(NULL); bit=AllocSignal(-1);
    if (bit<0) return 0;
    wake=1UL<<bit;
    GEMInputsDone=GEMInputsFailure=0;
    memset(GEMInputs,0,sizeof(GEMInputs));
    for (i=0;i<2;++i) { GEMInputs[i].config=&config[i]; stopping[i]=0; }
    if (!ExecAESAttach((struct MsgPort *)GEMInputsService) || appl_init()<0) {
        GEMInputsStop(); return 0;
    }
    /* Publish Task pointers before a worker can retire after failed startup. */
    Forbid();
    workers[0]=CreateTask("GEM Input A",1,(APTR)GEMInputOne,1024UL);
    workers[1]=CreateTask("GEM Input B",1,(APTR)GEMInputTwo,1024UL);
    Permit();
    if (!workers[0] || !workers[1]) { GEMInputsStop(); return 0; }
    while ((!GEMInputs[0].ready || !GEMInputs[1].ready) && !GEMInputsFailure) ExecYield();
    if (GEMInputsFailure) { GEMInputsStop(); return 0; }
    return 1;
}

WORD InputRecover(void)
{
    return ExecAESDiagnostic()==AES_INPUT_LOST;
}
