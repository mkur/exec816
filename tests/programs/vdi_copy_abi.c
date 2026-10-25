/* Focused emitted copy admission/result probe; hardware pixels run separately. */
#include "vdi-private.h"
#include "gem-drawing.h"
static struct ExecAESContext context;
static struct ExecVDIWorkstation station;
static struct AESWindowView view;
static WORD attached=1;
static UWORD calls,status,changes;
volatile UWORD CopyChecks;
struct ExecAESContext *ExecAESContext(void) { return attached ? &context:NULL; }
void ExecAESChanged(struct ExecAESContext *c,LONG l,LONG t,LONG r,LONG b)
{ (void)c;(void)l;(void)t;(void)r;(void)b;++changes; }
UWORD GemDrawingCopyBorrow(struct DisplayGrant *g,struct VbxeCopy *copy,UBYTE *edges)
{
    ++calls;
    if (g!=&station.grant || edges!=station.copyEdges || copy!=&station.copy ||
        copy->source.pitch!=320 || copy->destination.height!=240 ||
        copy->sourceX!=30 || copy->sourceY!=40 || copy->destinationX!=38 ||
        copy->destinationY!=32 || copy->width!=80 || copy->height!=48) return DISPLAY_BAD_ARGUMENT;
    return status;
}
#define CHECK(c) do {++CopyChecks;if(!(c))return __LINE__;} while(0)
LONG CopyProbe(void)
{
    WORD result;
    context.identity=1;context.workstation=&station;context.view=&view;
    station.handle=2;view.updates=1;view.pixelsReady=1;
    view.work.left=20;view.work.top=20;view.work.right=300;view.work.bottom=200;
    view.visibleCount=1;view.visible[0]=view.work;
    attached=0;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR);attached=1;
    context.busy=1;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_BUSY);context.busy=0;
    context.identity=0;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_IDENTITY);context.identity=1;
    CHECK(ExecVDICopyRect(3,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_IDENTITY);
    context.view=NULL;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_IDENTITY);context.view=&view;
    view.updates=0;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_BUSY);view.updates=1;
    CHECK(ExecVDICopyRect(2,30,40,-1,48,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_MALFORMED);
    CHECK(ExecVDICopyRect(2,30,40,80,-1,8,-8)==EXEC_VDI_COPY_ERROR && context.diagnostic==AES_MALFORMED);
    CHECK(ExecVDICopyRect(2,30,40,0,48,8,-8)==EXEC_VDI_COPY_DONE);
    CHECK(ExecVDICopyRect(2,30,40,80,0,8,-8)==EXEC_VDI_COPY_DONE);
    CHECK(ExecVDICopyRect(2,30,40,80,48,0,0)==EXEC_VDI_COPY_DONE);
    CHECK(ExecVDICopyRect(2,30,40,80,48,1,-8)==EXEC_VDI_COPY_REDRAW);
    view.pixelsReady=0;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_REDRAW);view.pixelsReady=1;
    CHECK(ExecVDICopyRect(2,32767,40,32767,48,8,-8)==EXEC_VDI_COPY_REDRAW);
    CHECK(ExecVDICopyRect(2,-32768,40,80,48,-32768,-8)==EXEC_VDI_COPY_REDRAW);
    CHECK(ExecVDICopyRect(2,30,40,80,48,8,-32)==EXEC_VDI_COPY_REDRAW);
    view.visibleCount=0;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_REDRAW);view.visibleCount=1;
    view.visible[0].right=100;CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_REDRAW);view.visible[0]=view.work;
    station.clipped=1;station.clip[0]=30;station.clip[1]=40;station.clip[2]=200;station.clip[3]=199;
    CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_REDRAW);station.clipped=0;
    CHECK(!calls && !changes && !context.request.paintFailed);
    result=ExecVDICopyRect(2,30,40,80,48,8,-8);
    CHECK(result==EXEC_VDI_COPY_DONE && calls==1 && changes==1 && !context.busy && context.diagnostic==AES_OK);
    status=DISPLAY_DEVICE_FAULT;
    CHECK(ExecVDICopyRect(2,30,40,80,48,8,-8)==EXEC_VDI_COPY_ERROR);
    CHECK(context.request.paintFailed && context.diagnostic==AES_DISPLAY_ERROR && calls==2 && changes==2 && !context.busy);
    return 0;
}
int main(void) { return 0; }
