#include "aes-private.h"
#include "vdi-private.h"
#include "gem-drawing.h"
#include "../../ports/gem4xe/raster/drawing.h"
#include <proto/exec.h>
static struct ExecAESContext context;
static struct ExecVDIWorkstation stations[2];
#define station stations[0]
static struct AESWindowView view;
static MFDB form;
static UWORD calls,changes,status,unexpected;
static WORD observed[6];
static WORD observedMode;
static struct ExecVDIUnit units[8];
static UWORD textCalls;
volatile UWORD CopyChecks;
struct ExecAESContext *ExecAESContext(void) { return &context; }
void ExecAESChanged(struct ExecAESContext *c,LONG l,LONG t,LONG r,LONG b)
{ (void)c;(void)l;(void)t;(void)r;(void)b;++changes; }
UWORD GemDrawingCopyBorrow(struct DisplayGrant *g,struct VbxeCopy *p,UBYTE *scratch)
{
    (void)g;(void)scratch;++calls;
    observed[0]=p->sourceX;observed[1]=p->sourceY;
    observed[2]=p->destinationX;observed[3]=p->destinationY;
    observed[4]=p->width;observed[5]=p->height;
    observedMode=S_ONLY;
    return status;
}
UWORD GemDrawingRasterBorrow(struct DisplayGrant *g,const struct GemRasterCopy *p,UBYTE *scratch)
{
    (void)g;(void)scratch;++calls;
    observed[0]=p->rect.sx;observed[1]=p->rect.sy;
    observed[2]=p->rect.dx;observed[3]=p->rect.dy;
    observed[4]=p->rect.width;observed[5]=p->rect.height;
    observedMode=p->mode;
    return status;
}
/* Unused PB branches still link; none may be called by a raster operation. */
APTR EXEC_CALL AllocMem(ULONG n,ULONG f) { (void)n;(void)f;++unexpected;return NULL; }
void EXEC_CALL FreeMem(APTR p,ULONG n) { (void)p;(void)n;++unexpected; }
BYTE EXEC_CALL AllocSignal(BYTE n) { (void)n;++unexpected;return -1; }
void EXEC_CALL FreeSignal(BYTE n) { (void)n;++unexpected; }
UWORD DisplayDelegate(struct DisplayGrant *g) { (void)g;++unexpected;return DISPLAY_BAD_ARGUMENT; }
BOOL ExecAESMouseCopy(struct ExecAESContext *c,const WORD *p)
{ (void)c;(void)p;++unexpected;return FALSE; }
WORD ExecAESMouseControl(struct ExecAESContext *c,WORD m,WORD r,WORD z)
{ (void)c;(void)m;(void)r;(void)z;++unexpected;return 0; }
void EXEC_CALL Forbid(void) { ++unexpected; }
void EXEC_CALL Permit(void) { ++unexpected; }
UWORD DisplayGrantClose(struct DisplayGrant *g) { (void)g;++unexpected;return 0; }
UWORD GemSolidRows(UWORD l,UWORD r) { (void)l;(void)r;return 240; }
UWORD GemDrawingSolidBorrow(struct DisplayGrant *g,UWORD l,UWORD t,UWORD r,UWORD b,UWORD p)
{ (void)g;++calls;observed[0]=l;observed[1]=t;observed[2]=r;observed[3]=b;observed[4]=p;return status; }
UWORD GemDrawingBorrow(struct DisplayGrant *g,UWORD l,UWORD t,UWORD r,UWORD b,void (*fn)(void *),void *p)
{ (void)g;(void)l;(void)t;(void)r;(void)b;(void)fn;units[textCalls++]=*(struct ExecVDIUnit *)p;return status; }
void GemVdiPaint(void *p) { (void)p;++unexpected; }
#define CHECK(c) do { ++CopyChecks;if (!(c)) return __LINE__; } while (0)
LONG CopyProbe(void)
{
    WORD a,b,attr[12],i,points[4]={100,40,20,10},clip[4]={30,15,70,30};
    WORD control[12]={38,0,99,0,99,0,2,0,0,0,0,0},ints[2]={1,5};
    VDIPB pb={control,ints,points,attr,attr+6};
    char longText[194];
    static const WORD tops[6]={34,36,34,33,33,40};
    context.identity=1;context.workstation=&station;context.view=&view;
    station.handle=2;station.writeMode=MD_REPLACE;station.textColor=6;station.fillColor=4;
    view.visibleCount=1;view.work.right=640;view.work.bottom=240;view.visible[0]=view.work;
    vqt_attributes(2,attr);
    CHECK(attr[0]==1 && attr[1]==6 && attr[2]==0 && attr[3]==0 && attr[4]==0);
    CHECK(attr[5]==1 && attr[6]==8 && attr[7]==6 && attr[8]==8 && attr[9]==8);
    attr[10]=1234;attr[11]=5678;vdi_call(&pb);
    CHECK(control[2]==2 && control[4]==6 && attr[10]==1234 && attr[11]==5678);
    vst_alignment(2,TA_RIGHT,TA_TOP,&a,&b);CHECK(a==2 && b==5);
    CHECK(station.hAlign==2 && station.vAlign==5 && !context.busy);
    context.workstation=&stations[1];stations[1].handle=2;
    vqt_attributes(2,attr);CHECK(attr[3]==0 && attr[4]==0);
    vst_alignment(2,TA_CENTRE,TA_HALF,&a,&b);
    context.workstation=&station;vqt_attributes(2,attr);CHECK(attr[3]==2 && attr[4]==5);
    vst_alignment(9,0,0,&a,&b);CHECK(context.diagnostic==AES_IDENTITY && station.hAlign==2);
    vst_alignment(2,3,-1,&a,&b);CHECK(a==0 && b==0 && context.diagnostic==AES_OK);
    control[0]=39;control[3]=2;vdi_call(&pb);
    CHECK(control[4]==2 && control[2]==0 && attr[0]==1 && attr[1]==5);
    control[3]=1;vdi_call(&pb);CHECK(context.diagnostic==AES_MALFORMED && station.hAlign==1);
    v_gtext(2,40,40,"ABC");CHECK(context.diagnostic==AES_BUSY && textCalls==0);
    view.updates=1;
    for(i=0;i<6;++i) {
        textCalls=0;vst_alignment(2,TA_LEFT,i,&a,&b);v_gtext(2,40,40,"ABC");
        CHECK(textCalls==1 && units[0].x==40 && units[0].y==tops[i]+6 && units[0].top==tops[i]);
    }
    textCalls=0;vst_alignment(2,TA_CENTRE,TA_TOP,&a,&b);v_gtext(2,40,40,"ABC");
    CHECK(textCalls==1 && units[0].x==28 && units[0].top==40);
    for(i=0;i<193;++i)longText[i]='A';longText[193]=0;
    textCalls=0;vst_alignment(2,TA_RIGHT,TA_TOP,&a,&b);v_gtext(2,600,40,longText);
    CHECK(textCalls==2 && units[0].x==-304 && units[1].x==336 && units[1].count==33);
    textCalls=0;v_gtext(2,600,40,"");CHECK(textCalls==0);
    control[0]=8;control[1]=1;control[3]=2;ints[0]='A';ints[1]='B';points[0]=100;points[1]=40;
    vdi_call(&pb);CHECK(textCalls==1 && units[0].x==84 && units[0].top==40);
    vs_clip(2,1,clip);points[0]=100;points[1]=40;points[2]=20;points[3]=10;
    vr_recfl(2,points);CHECK(calls==1 && observed[0]==30 && observed[1]==15 && observed[2]==71 && observed[3]==31 && observed[4]==4);
    control[0]=114;control[1]=2;control[3]=0;vdi_call(&pb);
    CHECK(calls==2 && control[2]==0 && control[4]==0);
    view.updates=0;vr_recfl(2,points);CHECK(calls==2 && context.diagnostic==AES_BUSY);view.updates=1;
    status=DISPLAY_DEVICE_FAULT;vr_recfl(2,points);
    CHECK(calls==3 && context.diagnostic==AES_DISPLAY_ERROR && context.request.paintFailed && !context.busy);
    CHECK(unexpected==0);
    return 0;
}
int main(void) { return 0; }
