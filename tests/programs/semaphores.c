#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <exec816/runtime.h>

#define DONE 0x10000UL
struct SignalSemaphore device __attribute__((aligned(2)));
volatile UWORD failures, checks, counter, completed;
UBYTE variant;
struct Task *parent;
static struct TaskLease lease;
static struct { struct Task *owner; UWORD depth; } composed;

static void Check(int okay) { ++checks; if (!okay) ++failures; }

/* Minimal fixture comparator, with caller identity cached outside timing. */
void ComposedPair(void)
{
    Forbid();
    if (composed.owner==parent) ++composed.depth;
    else { composed.owner=parent; composed.depth=1; }
    Permit();
    Forbid();
    if (!--composed.depth) composed.owner=NULL;
    Permit();
}

void NativePair(void)
{
    ObtainSemaphore(&device);
    ReleaseSemaphore(&device);
}

void Counter(void)
{
    ++counter;
    Signal(parent,DONE);
    ObtainSemaphore(&device);
    Check(AttemptSemaphore(&device)==1L);
    ReleaseSemaphore(&device);
    ReleaseSemaphore(&device);
    ++completed;
    Signal(parent,DONE);
    Wait(0);
}

int main(void)
{
    UWORD index;
    struct SignalSemaphore *farObject=(struct SignalSemaphore *)0x04fffaUL;
    struct Task *worker;
    parent=FindTask(NULL);
    Check(sizeof(device)==12);
    InitSemaphore(&device);
    Check(AttemptSemaphore(&device)==1L);
    ObtainSemaphore(&device);
    ReleaseSemaphore(&device);
    ReleaseSemaphore(&device);
#ifdef SEMAPHORE_APP
    /* Loaded-provider coverage uses each new import and exact LONG results. */
    for (index=0;index<8;++index) NativePair();
    Check(device.ss_Private[2]==0);
    return failures ? -999 : -321;
#else
    InitSemaphore(farObject);
    Check(AttemptSemaphore(farObject)==1L);
    ReleaseSemaphore(farObject);
    Check(AllocSignal(16)==16);
    ObtainSemaphore(&device);
    Forbid();
    worker=CreateTask("C semaphore counter",0,(APTR)Counter,1);
    Check(worker!=NULL);
    Check(RetainTask(worker,&lease)!=0);
    Permit();
    Check(Wait(DONE)==DONE);
    while (worker->tc_State!=TS_WAIT) ExecYield();
    Check(counter==1 && !completed);
    Check(AttemptSemaphore(&device)==1L);
    ReleaseSemaphore(&device);
    ReleaseSemaphore(&device);
    while (!completed) Wait(DONE);
    Check(completed==1);
    Forbid();
    Check(ReleaseTask(&lease)!=0);
    RemTask(worker);
    Permit();
    FreeSignal(16);
    if (variant) {
        for(index=0;index<32;++index) ComposedPair();
        for(index=0;index<32;++index) NativePair();
        composed.owner=parent; composed.depth=1;
        ObtainSemaphore(&device);
        for(index=0;index<32;++index) ComposedPair();
        for(index=0;index<32;++index) NativePair();
        ReleaseSemaphore(&device);
        composed.owner=NULL; composed.depth=0;
    }
    return failures;
#endif
}
