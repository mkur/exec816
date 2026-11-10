/* SPDX-License-Identifier: MIT */
#include "internal.h"
#include <string.h>
#include <exec816/program.h>
static struct ExecCRuntimeState state;
static UWORD acquired,finished,released,failed,shape;

static int no_arguments(void) { return -321; }
static int arguments(int argc,char **argv)
{ return argc==2 && !strcmp(argv[0],"probe") && !strcmp(argv[1],"two") && !argv[2] ? -321:11; }
static LONG initialize(struct ExecCRuntimeCall *call)
{
    acquired=1;finished=released=0;
    if (failed) { call->secondary=0x0000c219L;return 0; }
    return 1;
}
static LONG run(struct ExecCRuntimeCall *call)
{
    char *argv[3];
    (void)call;
    argv[0]="probe";argv[1]="two";argv[2]=NULL;
    return shape ? arguments(2,argv):no_arguments();
}
static void finish(struct ExecCRuntimeCall *call)
{ (void)call;finished=acquired; }
static void release(struct ExecCRuntimeCall *call)
{ (void)call;released=acquired;acquired=0; }
int main(void)
{
    struct ExecCRuntimeCall call;
    struct ExecCRuntimeOps ops;
    UWORD i;
    memset(&call,0,sizeof(call));memset(&ops,0,sizeof(ops));
    ops.initialize=initialize;ops.run=run;ops.finish=finish;ops.release=release;
    call.version=EXEC_CRT_VERSION;
    for (i=0;i<3;++i) {
        shape=i&1;failed=i==2;
        call.phase=EXEC_CRT_INIT;
        if (ExecCRuntimePhase(&state,&call,&ops)==failed) return 1;
        if (!failed) {
            call.phase=EXEC_CRT_RUN;
            if (!ExecCRuntimePhase(&state,&call,&ops) || call.primary!=-321) return 2;
        } else if (call.secondary!=0x0000c219L) return 3;
        call.phase=EXEC_CRT_RELEASE;
        if (ExecCRuntimePhase(&state,&call,&ops)) return 4;
        call.phase=EXEC_CRT_FINISH;
        if (!ExecCRuntimePhase(&state,&call,&ops) || !finished || released) return 5;
        call.phase=EXEC_CRT_RELEASE;
        if (!ExecCRuntimePhase(&state,&call,&ops) || !released || acquired) return 6;
    }
    call.version=EXEC_CRT_VERSION+1;call.phase=EXEC_CRT_INIT;
    if (ExecCRuntimePhase(&state,&call,&ops)) return 7;
    return -321;
}
