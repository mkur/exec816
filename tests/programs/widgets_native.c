#include <proto/exec.h>
#include <clib/alib_protos.h>
extern UWORD WidgetModelProbe(void);
static struct Task *supervisor;
volatile UWORD finished,failures,progress;
void WidgetWorker(void)
{
    UWORD i;
    for (i=0;i<32;i++) {
        failures+=WidgetModelProbe();
        progress=i+1;
    }
    Forbid();
    finished=1;
    Signal(supervisor,1UL<<31);
    RemTask(NULL);
}
int main(void)
{
    struct Task *worker;
    supervisor=FindTask(NULL);
    if (AllocSignal(31)!=31) return 1;
    Forbid();
    worker=CreateTask("AES objects",0,(APTR)WidgetWorker,2560UL);
    Permit();
    if (worker) while (!finished) Wait(1UL<<31);
    FreeSignal(31);
    return !worker || failures;
}
