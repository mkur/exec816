/* Public invalidation and generated C/Action record interchange. */
#include <exec816/aes.h>
#include <string.h>
volatile UWORD DamageChecks;
struct AESRequest DamageWire;
static struct ExecAESContext context;
static struct AESWindowView view;
struct ExecAESContext *ExecAESContext(void) { return &context; }
extern void ExecAESChanged(struct ExecAESContext *,LONG,LONG,LONG,LONG);
#define CHECK(x) do { if (!(x)) return __LINE__; ++DamageChecks; } while (0)

LONG EXEC_CALL DamageProbe(ULONG unused)
{
    UWORD i;
    (void)unused;
    CHECK(DamageWire.invalidationCount==7 && DamageWire.invalidations[6].handle==0x7f12);
    memset(&context,0,sizeof(context));memset(&view,0,sizeof(view));
    context.view=&view;context.views[0]=&view;
    view.handle=1;view.updates=1;view.paintEpoch=7;view.pixelsReady=1;
    view.work.left=10;view.work.top=20;view.work.right=90;view.work.bottom=100;
    CHECK(ExecAESWindowView(1)==&view && ExecAESWindowView(2)==NULL);
    CHECK(ExecAESInvalidate(1,0,0,0,0));
    CHECK(view.changed==AES_CHANGE_DECLARED && !context.request.invalidationCount);
    CHECK(ExecAESInvalidate(1,12,22,10,8));
    CHECK(context.request.invalidationCount==1);
    CHECK(context.request.invalidations[0].handle==1 && context.request.invalidations[0].epoch==7);
    CHECK(context.request.invalidations[0].rect.left==12 && context.request.invalidations[0].rect.right==22);
    CHECK(!context.request.paintCount && !(view.changed&AES_CHANGE_UNDECLARED));
    context.request.paintCount=1;context.request.paints[0]=context.request.invalidations[0];
    CHECK(ExecAESInvalidate(1,12,22,10,8) && !context.request.paintCount);
    ExecAESChanged(&context,13,23,20,29);
    CHECK(!(view.changed&AES_CHANGE_UNDECLARED));
    ExecAESChanged(&context,50,50,60,60);
    CHECK(view.changed&AES_CHANGE_UNDECLARED);
    CHECK(!ExecAESInvalidate(1,0,0,-1,4) && context.diagnostic==AES_MALFORMED);
    CHECK(context.request.invalidationCount==2);
    context.diagnostic=0;
    CHECK(ExecAESInvalidate(1,-32768,-32768,32767,32767));
    CHECK(context.request.invalidationCount==2);
    CHECK(ExecAESInvalidate(1,80,90,32767,32767));
    CHECK(context.request.invalidations[2].rect.right==90 && context.request.invalidations[2].rect.bottom==100);
    for (i=3;i<AES_INVALIDATION_REPORTS;++i) CHECK(ExecAESInvalidate(1,12,22,1,1));
    CHECK(!ExecAESInvalidate(1,12,22,1,1) && context.diagnostic==AES_OVERFLOW);
    CHECK(context.request.invalidationCount==AES_INVALIDATION_REPORTS && !context.request.paintCount);
    view.updates=0;
    CHECK(!ExecAESInvalidate(1,12,22,1,1));
    DamageWire.invalidationCount=2;
    DamageWire.invalidations[1].epoch=0x12345678UL;
    DamageWire.invalidations[1].rect.right=123;
    return 0;
}
int main(void) { return 0; }
