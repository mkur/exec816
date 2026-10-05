#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <exec/widget-types.h>
struct WidgetPacket WidgetLayoutPacket;
/* Action! writes every array element; C verifies stride/signed fields and
   writes different values back for the Action! caller to check. */
UWORD WidgetPacketLayout(void)
{
    UWORD i;
    if (WidgetLayoutPacket.damageCount!=WIDGET_DAMAGE_RECTS) return 1;
    for (i=0;i<WIDGET_DAMAGE_RECTS;i++) {
        struct WidgetDamageRect *r=&WidgetLayoutPacket.damage[i];
        if (r->left!=-100-(WORD)i || r->top!=100+i || r->right!=200+i || r->bottom!=300+i) return 1;
        r->left=-300-i;r->top=500+i;r->right=600+i;r->bottom=700+i;
    }
    return 0;
}
extern UWORD WidgetModelProbe(void);
#ifdef WIDGET_STATE_PROBE
extern UWORD WidgetStateProbe(void);
#endif
#ifdef WIDGET_INPUT_PROBE
extern UWORD WidgetInputProbe(void);
#endif
static struct Task *supervisor;
volatile UWORD finished,failures,progress;
void WidgetWorker(void)
{
    UWORD i;
    for (i=0;i<32;i++) {
        failures+=WidgetModelProbe();
#ifdef WIDGET_STATE_PROBE
        failures+=WidgetStateProbe();
#endif
#ifdef WIDGET_INPUT_PROBE
        failures+=WidgetInputProbe();
#endif
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
