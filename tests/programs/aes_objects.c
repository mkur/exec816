#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static void check(WORD okay) {
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}
#define CHECK(x) check((x)!=0)
static OBJECT tree[]={
    {-1,1,4,G_BOX,0,0,0x1170,48,48,160,88},
    {2,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,SELECTED,0,8,8,64,16},
    {3,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,0,0,80,8,64,16},
    {4,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT,0,0,8,40,64,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|LASTOB,DISABLED,0,80,40,64,16}
};
void AESClientOne(void) { }
void AESClientTwo(void) { }
UWORD AESRun(void)
{
    WORD x,y,w,h,next,key,handle=1,window;
    WORD in[11]={1,1,1,1,1,1,1,1,1,1,2},out[57];
    WORD control[5]={44,1,3,1,0},global[15],args[8]={2},reply[5];
    LONG address=(LONG)(ULONG)tree;
    AESPB pb={control,global,args,reply,&address,0};
    ULONG available=AvailMem(0);
    tree[1].ob_spec=(ULONG)"Small"; tree[2].ob_spec=(ULONG)"Large";
    tree[3].ob_spec=(ULONG)"Apply"; tree[4].ob_spec=(ULONG)"Locked";
    CHECK(sizeof(OBJECT)==24 && sizeof(GRECT)==8);
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    CHECK(objc_offset(tree,2,&x,&y) && x==128 && y==56);
    aes_call(&pb); CHECK(reply[0]==1 && reply[1]==128 && reply[2]==56);
    CHECK(objc_find(tree,0,8,130,60)==2);
    tree[2].ob_flags|=HIDETREE; CHECK(objc_find(tree,0,8,130,60)==0);
    tree[2].ob_flags&=~HIDETREE;
    CHECK(form_button(tree,2,1,&next)==1 && tree[2].ob_state==SELECTED && tree[1].ob_state==0);
    CHECK(form_button(tree,4,1,&next)==1 && tree[4].ob_state==DISABLED);
    CHECK(form_keybd(tree,1,1,0x0f09,&next,&key)==1 && next==2 && key==0);
    CHECK(form_keybd(tree,1,1,0x1c0d,&next,&key)==0 && next==3 && key==0);
    CHECK(form_keybd(tree,2,2,0x0f00,&next,&key)==1 && next==1);
    CHECK(objc_change(tree,1,0,0,0,640,240,SELECTED,0));
    CHECK(!objc_draw(tree,0,8,0,0,640,240) && ExecAESDiagnostic()==AES_BUSY);
    v_opnvwk(in,&handle,out); CHECK(handle>0);
    window=wind_create(NAME|CLOSER|MOVER,0,0,192,120); CHECK(window>0);
    CHECK(wind_open(window,32,24,192,120));
    CHECK(form_center(tree,&x,&y,&w,&h) && x==48 && y==44 && w==160 && h==88);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(objc_draw(tree,0,8,45,48,100,31));
    CHECK(objc_change(tree,2,0,0,0,640,240,0,1));
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_close(window)); CHECK(wind_delete(window));
    v_clsvwk(handle); CHECK(appl_exit()); CHECK(ExecAESDetach());
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
