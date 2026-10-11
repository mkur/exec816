#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>
#include <string.h>
#include <stddef.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static void check(WORD okay) {
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
}
#define CHECK(x) check((x)!=0)
volatile UWORD ObjectPhase,ObjectGo,ObjectProbe,ObjectBorrows,ObjectRows[4],ObjectLists;
/* Test-only adapter hooks; no counters are linked into the demo. */
void ObjectBorrowProbe(UWORD rows)
{
    if (ObjectProbe) {
        if (ObjectBorrows<4) ObjectRows[ObjectBorrows]=rows;
        ++ObjectBorrows;
    }
}
void ObjectListProbe(const UBYTE *p,UWORD count)
{
    ULONG work=0;
    UWORD i,width,rows;
    if (!ObjectProbe) return;
    ++ObjectLists;
    CHECK(count && count<=64);
    for (i=0;i<count;++i,p+=21) {
        width=((UWORD)p[12]|((UWORD)p[13]<<8))+1;
        rows=(UWORD)p[14]+1;
        CHECK(width<=512 && rows<=256);
        work+=(ULONG)width*rows*(p[20] ? 3:2);
    }
    CHECK(work<=8192);
}
static WORD unit_probe(WORD window)
{
    static const WORD heights[]={16,17,31,32,33,14,16,16,26,33,12};
    static OBJECT background={-1,-1,-1,G_BOX,LASTOB,0,0x1170,8,40,624,184};
    static OBJECT object={-1,-1,-1,G_BOX,LASTOB,0,0x1178,17,49,608,16};
    WORD i,j;
    CHECK(wind_close(window));CHECK(wind_delete(window));
    window=wind_create(NAME|CLOSER|MOVER,0,0,640,208);CHECK(window>0);
    CHECK(wind_open(window,0,24,640,208));
    for (i=0;i<11;++i) {
        object.ob_height=heights[i];object.ob_type=i>=5 && i<=8 ? G_BUTTON:G_BOX;
        object.ob_flags=LASTOB|(i>=6 && i<=8 ? EXIT:0)|(i==7 || i==8 ? DEFAULT:0);
        object.ob_state=i==8 ? SELECTED|DISABLED:i==10 ? SELECTED:0;
        object.ob_spec=object.ob_type==G_BUTTON ? (ULONG)"Wide":0x1178;
        CHECK(wind_update(BEG_UPDATE));
        CHECK(objc_draw(&background,0,0,0,0,640,240));
        ObjectBorrows=ObjectLists=0;
        for (j=0;j<4;++j) ObjectRows[j]=0;
        ObjectProbe=1;
        CHECK(objc_draw(&object,0,0,i==9 ? 19:0,i==9 ? 52:0,i==9 ? 603:640,i==9 ? 24:240));
        ObjectProbe=0;
        CHECK(ObjectBorrows==(i==4 ? 3:i==9 ? 2:1));
        if (i==4) CHECK(ObjectRows[0]==16 && ObjectRows[1]==16 && ObjectRows[2]==1);
        if (i==9) CHECK(ObjectRows[0]==16 && ObjectRows[1]==8);
        if (i==3 || i==8) CHECK(ObjectLists>1);
        CHECK(wind_update(END_UPDATE));
        ObjectPhase=i+1;while (ObjectGo<ObjectPhase) ExecYield();
    }
    return window;
}
static void box_probe(void)
{
    /* type, thickness, width, height, colour word, state, damage edge */
    static const WORD cases[][7]={
        {G_BOX,1,41,25,0x1178,0,0},{G_BOX,3,41,25,0x2173,0,0},
        {G_BOX,-1,41,25,0x0172,0,0},{G_BOX,-3,41,25,0x4170,0,0},
        {G_BOX,0,41,25,0x1189,0,0},{G_BOX,0,41,25,0x1170,0,0},
        {G_BOX,2,5,5,0x0172,0,0},{G_BOX,3,6,6,0x1178,0,0},
        {G_BOX,3,5,5,0x1178,0,0},{G_IBOX,2,41,25,0x1178,0,0},
        {G_BOX,2,41,25,0x2173,SELECTED|DISABLED,0},
        {G_BOX,-2,41,25,0x1178,SELECTED,0},
        {G_BOX,-3,41,25,0x2173,0,1},{G_BOX,-3,41,25,0x2173,0,2},
        {G_BOX,-3,41,25,0x2173,0,3},{G_BOX,-3,41,25,0x2173,0,4},
        {G_BOX,3,41,33,0x2173,0,0},{G_BOX,-2,41,33,0x1178,DISABLED,0},
        {G_BOX,2,41,25,0x1140,0,0},{G_BOX,1,90,42,0x1178,0,0},
        {G_BOX,-3,41,25,0x2173,0,5}
    };
    static OBJECT background={-1,-1,-1,G_BOX,LASTOB,0,0x1175,8,40,624,184};
    static OBJECT objects[3]={
        {-1,-1,-1,G_BOX,LASTOB,0,0,57,81,41,25},
        {2,-1,-1,G_BOX,0,0,0xff1172UL,10,8,30,16},
        {0,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT|LASTOB,SELECTED|DISABLED,0,25,12,48,16}
    };
    WORD i,l,t,r,b,edge;
    struct AESWindowView *view;
    struct AESRect visible;
    objects[2].ob_spec=(ULONG)"Wide";
    for (i=0;i<21;++i) {
        objects[0].ob_type=cases[i][0];objects[0].ob_width=cases[i][2];objects[0].ob_height=cases[i][3];
        objects[0].ob_spec=((ULONG)(UBYTE)cases[i][1]<<16)|(UWORD)cases[i][4];
        objects[0].ob_state=cases[i][5];objects[0].ob_head=i==19 ? 1:-1;objects[0].ob_tail=i==19 ? 2:-1;
        objects[0].ob_flags=i==19 ? 0:LASTOB;
        edge=cases[i][6];l=edge==1 ? 58:8;t=edge==3 ? 82:40;
        r=edge==2 ? 97:632;b=edge==4 ? 105:224;
        CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(&background,0,0,0,0,640,240));
        view=ExecAESContext()->view;visible=view->visible[0];
        if (edge==5) {
            /* Narrow the owned snapshot into two disjoint admitted regions. */
            view->visible[1]=visible;view->visible[0].right=73;
            view->visible[1].left=79;view->visibleCount=2;
        }
        ObjectBorrows=ObjectLists=0;ObjectProbe=1;
        CHECK(objc_draw(objects,0,8,l,t,r-l,b-t));ObjectProbe=0;
        if (edge==5) { CHECK(ObjectBorrows==2);view->visible[0]=visible;view->visibleCount=1; }
        CHECK(wind_update(END_UPDATE));
        ObjectPhase=12+i;while (ObjectGo<ObjectPhase) ExecYield();
    }
}
static OBJECT tree[]={
    {-1,1,4,G_BOX,0,0,0x1170,48,48,160,88},
    {2,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,SELECTED,0,8,8,64,16},
    {3,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,0,0,80,8,64,16},
    {4,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT,0,0,8,40,64,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|LASTOB,DISABLED,0,80,40,64,16}
};
volatile UWORD TEDPhase,TEDGo;
static TEDINFO ted[3];
static OBJECT textTree[]={
    {-1,1,3,G_BOX,0,0,0x1170,48,44,160,88},
    {2,-1,-1,G_BOXTEXT,0,0,0,8,8,128,8},
    {3,-1,-1,G_BOXTEXT,0,0,0,8,32,128,8},
    {0,-1,-1,G_TEXT,LASTOB,0,0,8,56,128,8}
};
static void text_probe(void)
{
    UBYTE *storage=AllocMem(131088UL,MEMF_PUBLIC|MEMF_LINEAR);
    char *text;
    WORD i;
    CHECK(storage!=NULL);
    if (!storage) return;
    text=(char *)((((ULONG)storage+65535UL)&0xffff0000UL)+65532UL);
    CHECK((ULONG)text>65535UL && ((ULONG)text&65535UL)==65532UL);
    strcpy(text,"-2147483647");
    for (i=0;i<3;++i) {
        ted[i].te_ptext=(ULONG)text;ted[i].te_font=IBM;ted[i].te_just=i;
        ted[i].te_color=0x1180;ted[i].te_thickness=-1;ted[i].te_txtlen=12;
        textTree[i+1].ob_spec=(ULONG)&ted[i];
    }
    CHECK(sizeof(TEDINFO)==28 && offsetof(TEDINFO,te_thickness)==22);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(objc_draw(textTree,0,8,0,0,640,240));
    CHECK(wind_update(END_UPDATE));
    TEDPhase=1;while (TEDGo<1) ExecYield();
    strcpy(text,"          7");
    CHECK(wind_update(BEG_UPDATE));
    for (i=1;i<=3;++i) CHECK(objc_draw(textTree,i,0,0,0,640,240));
    CHECK(wind_update(END_UPDATE));
    TEDPhase=2;while (TEDGo<2) ExecYield();
    CHECK(wind_update(BEG_UPDATE));
    CHECK(objc_draw(textTree,0,8,53,49,57,18));
    CHECK(wind_update(END_UPDATE));
    TEDPhase=3;while (TEDGo<3) ExecYield();
    FreeMem(storage,131088UL);
}
volatile UWORD EditPhase,EditGo;
static char editText[16]="ab";
static TEDINFO editTed={(ULONG)editText,(ULONG)"__-__",(ULONG)"X",IBM,0,TE_LEFT,0x1180,0,-1,16,6};
static OBJECT editTree[]={
    {-1,1,3,G_BOX,0,0,0x1170,48,44,160,88},
    {2,-1,-1,G_BOXTEXT,EDITABLE,0,(ULONG)&editTed,8,8,64,16},
    {3,-1,-1,G_BUTTON,SELECTABLE|DEFAULT|EXIT,0,(ULONG)"OK",8,40,48,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|LASTOB,0,(ULONG)"Cancel",80,40,64,16}
};
static void edit_probe(void)
{
    WORD index,next,key,i;
    WORD control[5]={46,4,2,1,0},global[15],args[4]={1,0,0,ED_INIT},reply[2];
    LONG address=(LONG)(ULONG)editTree;
    AESPB pb={control,global,args,reply,&address,0};
    CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(editTree,0,8,0,0,640,240));CHECK(wind_update(END_UPDATE));
    aes_call(&pb);index=reply[1];CHECK(reply[0] && index==2);
    CHECK(form_button(editTree,1,1,&next)==1 && next==1 && editTree[1].ob_state==0);
    CHECK(form_keybd(editTree,1,1,32,&next,&key)==1 && key==32);
    CHECK(form_keybd(editTree,1,1,9,&next,&key)==1 && next==2 && !key);
    CHECK(form_keybd(editTree,2,2,0x0f00,&next,&key)==1 && next==1 && !key);
    CHECK(form_keybd(editTree,1,1,13,&next,&key)==0 && next==2 && !key);
    CHECK(objc_edit(editTree,1,0x4b00,&index,ED_CHAR) && index==1);
    CHECK(objc_edit(editTree,1,'Z',&index,ED_CHAR) && !strcmp(editText,"aZb") && index==2);
    CHECK(objc_edit(editTree,1,8,&index,ED_CHAR) && !strcmp(editText,"ab") && index==1);
    CHECK(objc_edit(editTree,1,0x5300,&index,ED_CHAR) && !strcmp(editText,"a"));
    CHECK(objc_edit(editTree,1,0x4700,&index,ED_CHAR) && index==0);
    CHECK(objc_edit(editTree,1,0x537f,&index,ED_CHAR) && !editText[0]);
    CHECK(objc_edit(editTree,1,27,&index,ED_CHAR) && !editText[0] && !index);
    editTed.te_pvalid=(ULONG)"9A";
    CHECK(objc_edit(editTree,1,'x',&index,ED_CHAR) && !index);
    CHECK(objc_edit(editTree,1,'2',&index,ED_CHAR) && index==1);
    CHECK(objc_edit(editTree,1,'b',&index,ED_CHAR) && !strcmp(editText,"2B"));
    CHECK(objc_edit(editTree,1,'c',&index,ED_CHAR) && !strcmp(editText,"2BC"));
    editTed.te_pvalid=(ULONG)"X";editTed.te_txtlen=5;
    CHECK(objc_edit(editTree,1,'d',&index,ED_CHAR) && !strcmp(editText,"2BCd"));
    CHECK(objc_edit(editTree,1,'e',&index,ED_CHAR) && !strcmp(editText,"2BCd") && index==4);
    editTree[1].ob_type=G_FBOXTEXT;editTed.te_txtlen=16;
    CHECK(objc_edit(editTree,1,'f',&index,ED_CHAR) && !strcmp(editText,"2BCd") && index==4);
    EditPhase=1;while (EditGo<1) ExecYield();
    editTree[1].ob_type=G_BOXTEXT;strcpy(editText,"0123456789ab");
    CHECK(objc_edit(editTree,1,0,&index,ED_INIT) && index==12);
    CHECK(ExecAESContext()->editScroll==5);
    EditPhase=2;while (EditGo<2) ExecYield();
    CHECK(objc_edit(editTree,1,0x4700,&index,ED_CHAR) && index==0);
    CHECK(objc_edit(editTree,1,0x4f00,&index,ED_CHAR) && index==12);
    CHECK(objc_edit(editTree,1,0,&index,ED_END) && !ExecAESContext()->editTree);
    EditPhase=3;while (EditGo<3) ExecYield();
    CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(editTree,1,0,57,54,18,10));CHECK(wind_update(END_UPDATE));
    EditPhase=4;while (EditGo<4) ExecYield();
    editTree[1].ob_flags|=HIDETREE;
    CHECK(form_keybd(editTree,3,3,9,&next,&key)==1 && next==2);
    for (i=0;i<16;++i) editText[i]=0;
}
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
    text_probe();edit_probe();window=unit_probe(window);box_probe();
    CHECK(wind_close(window)); CHECK(wind_delete(window));
    v_clsvwk(handle); CHECK(appl_exit()); CHECK(ExecAESDetach());
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
