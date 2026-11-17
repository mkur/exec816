#include "aes-private.h"
#include "vdi-private.h"
#include "gem-drawing.h"
#include "../../ports/gem4xe/raster/drawing.h"
#include <proto/exec.h>
static struct ExecAESContext context;
static struct ExecVDIWorkstation station;
static struct AESWindowView view;
static MFDB form;
static UWORD calls,changes,status,unexpected;
static WORD observed[6];
static WORD observedMode;
volatile UWORD CopyChecks;
struct ExecAESContext *ExecAESContext(void) { return &context; }
void ExecAESChanged(struct ExecAESContext *c,LONG l,LONG t,LONG r,LONG b)
{ (void)c;(void)l;(void)t;(void)r;(void)b;++changes; }
UWORD GemDrawingCopyBorrow(struct DisplayGrant *g,struct VbxeCopy *p)
{
    (void)g;++calls;
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
UWORD GemSolidRows(UWORD l,UWORD r) { (void)l;(void)r;++unexpected;return 1; }
UWORD GemDrawingSolidBorrow(struct DisplayGrant *g,UWORD l,UWORD t,UWORD r,UWORD b,UWORD p)
{ (void)g;(void)l;(void)t;(void)r;(void)b;(void)p;++unexpected;return 0; }
UWORD GemDrawingBorrow(struct DisplayGrant *g,UWORD l,UWORD t,UWORD r,UWORD b,void (*fn)(void *),void *p)
{ (void)g;(void)l;(void)t;(void)r;(void)b;(void)fn;(void)p;++unexpected;return 0; }
void GemVdiPaint(void *p) { (void)p;++unexpected; }
#define CHECK(c) do { ++CopyChecks;if (!(c)) return __LINE__; } while (0)
LONG CopyProbe(void)
{
    WORD points[8]={30,40,109,87,38,32,117,79},mode=S_ONLY;
    WORD control[12]={109,4,77,1,77,0,2,0,0,0,0,0};
    VDIPB pb={control,&mode,points,NULL,NULL};
    ULONG address=(ULONG)&form;
    context.identity=1;context.workstation=&station;context.view=&view;
    station.handle=2;view.updates=1;view.pixelsReady=0;
    view.work.left=20;view.work.top=20;view.work.right=300;view.work.bottom=200;
    view.visibleCount=1;view.visible[0]=view.work;
    CHECK(sizeof(MFDB)==20); /* Offsets are checked from the emitted layout object. */
    vro_cpyfm(2,S_ONLY,points,&form,NULL);
    CHECK(context.diagnostic==AES_OK && calls==1 && changes==1 && !context.busy);
    CHECK(observed[0]==30 && observed[1]==40 && observed[2]==38 && observed[3]==32 && observed[4]==80 && observed[5]==48);
    control[7]=(WORD)address;control[8]=(WORD)(address>>16);
    vdi_call(&pb);
    CHECK(context.diagnostic==AES_OK && calls==2 && control[2]==0 && control[4]==0);
    points[4]=31;points[6]=110;vro_cpyfm(2,S_ONLY,points,NULL,&form);
    CHECK(context.diagnostic==AES_OK && calls==3 && observed[2]==31);
    view.updates=0;vro_cpyfm(2,S_ONLY,points,NULL,NULL);
    CHECK(context.diagnostic==AES_BUSY && calls==3);view.updates=1;
    vro_cpyfm(9,S_ONLY,points,NULL,NULL);CHECK(context.diagnostic==AES_IDENTITY && calls==3);
    mode=16;vdi_call(&pb);CHECK(context.diagnostic==AES_UNSUPPORTED && calls==3);mode=S_ONLY;
    control[1]=3;vdi_call(&pb);CHECK(context.diagnostic==AES_MALFORMED && calls==3);control[1]=4;
    form.fd_addr=(void *)1;vro_cpyfm(2,S_ONLY,points,&form,NULL);
    CHECK(context.diagnostic==AES_UNSUPPORTED && calls==3);form.fd_addr=NULL;
    station.clipped=1;station.clip[0]=40;station.clip[1]=35;station.clip[2]=99;station.clip[3]=99;
    vro_cpyfm(2,S_ONLY,points,NULL,NULL);
    CHECK(context.diagnostic==AES_OK && calls==4 && observed[0]==39 && observed[1]==43 && observed[2]==40 && observed[3]==35 && observed[4]==60 && observed[5]==45);
    station.clipped=0;
    view.visibleCount=3;
    view.visible[0].left=20;view.visible[0].top=20;view.visible[0].right=70;view.visible[0].bottom=55;
    view.visible[1].left=80;view.visible[1].top=20;view.visible[1].right=300;view.visible[1].bottom=55;
    view.visible[2].left=20;view.visible[2].top=65;view.visible[2].right=300;view.visible[2].bottom=200;
    vro_cpyfm(2,S_ONLY,points,NULL,NULL);
    CHECK(context.diagnostic==AES_OK && calls==7 && observed[2]==31 && observed[3]==65 && observed[4]==80 && observed[5]==15);
    view.visibleCount=1;view.visible[0]=view.work;
    status=DISPLAY_DEVICE_FAULT;vro_cpyfm(2,S_ONLY,points,NULL,NULL);
    CHECK(context.diagnostic==AES_DISPLAY_ERROR && context.request.paintFailed && !context.busy && calls==8);
    status=DISPLAY_OK;context.request.paintFailed=0;
    form.fd_addr=(void *)0x100000UL;form.fd_w=640;form.fd_h=240;form.fd_wdwidth=40;form.fd_nplanes=4;
    context.view=NULL;
    vro_cpyfm(2,S_ONLY,points,&form,&form);
    CHECK(context.diagnostic==AES_OK && calls==9 && changes==8);
    form.fd_stand=1;vro_cpyfm(2,S_ONLY,points,&form,&form);
    CHECK(context.diagnostic==AES_UNSUPPORTED && calls==9);
    form.fd_stand=0;
    vro_cpyfm(2,S_XOR_D,points,&form,&form);
    CHECK(context.diagnostic==AES_OK && calls==10 && observedMode==S_XOR_D);
    vro_cpyfm(2,D_ONLY,points,&form,&form);
    CHECK(context.diagnostic==AES_OK && calls==10);
    points[4]=points[0];points[5]=points[1];points[6]=points[2];points[7]=points[3];
    vro_cpyfm(2,S_XOR_D,points,&form,&form);
    CHECK(context.diagnostic==AES_OK && calls==11);
    vro_cpyfm(2,S_ONLY,points,&form,&form);
    CHECK(context.diagnostic==AES_OK && calls==11);
    CHECK(unexpected==0);
    return 0;
}
int main(void) { return 0; }
