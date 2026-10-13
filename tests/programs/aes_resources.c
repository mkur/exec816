#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include <string.h>
ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,ResourceStatus;
volatile LONG ResourceError;
volatile ULONG ResourceHeapWarm,ResourceHeapReturned;
static void check(WORD okay) { ++AESChecks;if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=AESChecks; } }
#define CHECK(x) check((x)!=0)
void AESClientOne(void) { }
void AESClientTwo(void) { }
static struct FileInfoBlock info;
static WORD work_in[11]={1,1,1,1,1,1,1,1,1,1,2},work_out[57];
static void text_resource(void)
{
    OBJECT *tree,*again;
    TEDINFO *ted;
    WORD handle=1,window,i;
    const char *bad[]={"D1:TEDBAD.RSC","D1:TEDSHORT.RSC","D1:TEDSTR.RSC"};
    CHECK(rsrc_load("D1:CALC.RSC"));
    if (!rsrc_gaddr(R_TREE,0,(void **)&tree)) { CHECK(0); return; }
    CHECK(tree[0].ob_width==184 && tree[0].ob_height==160 && tree[2].ob_type==G_BOXTEXT);
    ted=(TEDINFO *)(ULONG)tree[2].ob_spec;
    CHECK((ULONG)ted>65535UL && ted->te_ptext>65535UL);
    CHECK(ted->te_font==IBM && ted->te_just==TE_RIGHT && ted->te_thickness==-1);
    CHECK(ted->te_txtlen==12 && ted->te_tmplen==12);
    CHECK(!strcmp((char *)(ULONG)ted->te_ptext,"           ") &&
          !strcmp((char *)(ULONG)ted->te_ptmplt,"___________") &&
          !strcmp((char *)(ULONG)ted->te_pvalid,"9"));
    strcpy((char *)(ULONG)ted->te_ptext,"         42");
    for (i=0;i<3;++i) {
        CHECK(!rsrc_load(bad[i]));
        CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && tree==again);
        CHECK(!strcmp((char *)(ULONG)ted->te_ptext,"         42"));
    }
    v_opnvwk(work_in,&handle,work_out);CHECK(handle>0);
    window=wind_create(NAME|CLOSER|MOVER,0,0,200,184);CHECK(window>0);
    CHECK(wind_open(window,312,24,200,184));
    tree[0].ob_x=320;tree[0].ob_y=40;
    CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(tree,0,MAX_DEPTH,320,40,184,160));
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_close(window));CHECK(wind_delete(window));v_clsvwk(handle);
    for (i=0;i<3;++i) {
        CHECK(rsrc_load("D1:SHARED.RSC"));
        CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
        CHECK(tree[1].ob_spec==tree[2].ob_spec);
        ted=(TEDINFO *)(ULONG)tree[2].ob_spec;
        CHECK(!strcmp((char *)(ULONG)ted->te_ptext,"           "));
        CHECK(rsrc_free());
    }
    /* Deliberately leave the final resource to ordinary appl_exit cleanup. */
    CHECK(rsrc_load("D1:CALC.RSC"));
}
static void editable_resource(void)
{
    OBJECT *tree,*again;
    TEDINFO *ted;
    WORD i,index,handle=1,window,words[8]={123,2,3,4,5,6,7,321};
    const char *bad[]={"D1:EDCAP.RSC","D1:EDEXT.RSC","D1:EDNUL.RSC","D1:EDTYPE.RSC"};
    CHECK(rsrc_load("D1:EDIT.RSC"));CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    ted=(TEDINFO *)(ULONG)tree[1].ob_spec;
    CHECK(tree[1].ob_type==G_FBOXTEXT && (tree[1].ob_flags&EDITABLE));
    CHECK(ted->te_txtlen==12 && ted->te_tmplen==6 && !strcmp((char *)ted->te_ptext,"2B"));
    v_opnvwk(work_in,&handle,work_out);CHECK(handle>0);
    window=wind_create(NAME|CLOSER|MOVER,0,0,184,104);CHECK(window>0);
    CHECK(wind_open(window,312,24,184,104));tree[0].ob_x=320;tree[0].ob_y=40;
    CHECK(objc_edit(tree,1,0,&index,ED_INIT) && index==2);
    CHECK(objc_edit(tree,1,'c',&index,ED_CHAR) && !strcmp((char *)ted->te_ptext,"2BC"));
    CHECK(objc_edit(tree,1,0,&index,ED_END));
    /* The synchronous loop borrows the fixed-up writable resource tree. */
    CHECK(appl_write(ExecAESContext()->gemId,16,words));
    CHECK(form_do(tree,1)==-1 && ExecAESDiagnostic()==AES_PENDING);
    CHECK(evnt_mesag(words) && words[0]==123 && words[7]==321);
    CHECK(!ExecAESContext()->form && !ExecAESContext()->editTree);
    CHECK(!strcmp((char *)ted->te_ptext,"2BC"));
    for (i=0;i<4;++i) {
        CHECK(!rsrc_load(bad[i]));CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && again==tree);
        CHECK(!strcmp((char *)ted->te_ptext,"2BC") && ted->te_txtlen==12);
    }
    CHECK(wind_close(window));CHECK(wind_delete(window));v_clsvwk(handle);
}
volatile UWORD IconPhase,IconGo;
static void icon_resource(void)
{
    static UWORD mask[32],bits[32];
    static ICONBLK compiled;
    static OBJECT background={-1,-1,-1,G_BOX,LASTOB,0,0x1175,8,40,624,184};
    static OBJECT icon={-1,-1,-1,G_ICON,LASTOB,0,0,57,81,64,32};
    const char *bad[]={"D1:ICWIDTH.RSC","D1:ICHEIGHT.RSC","D1:ICEXT.RSC"};
    OBJECT *tree,*again;
    ICONBLK *loaded,*shared;
    WORD i,window,handle=1;
    CHECK(sizeof(ICONBLK)==34);
    CHECK(rsrc_load("D1:ICON.RSC"));CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    loaded=(ICONBLK *)(ULONG)tree[1].ob_spec;shared=(ICONBLK *)(ULONG)tree[2].ob_spec;
    CHECK(loaded->ib_pmask==shared->ib_pmask && loaded->ib_pdata==shared->ib_pdata);
    CHECK(*(const UWORD *)(ULONG)loaded->ib_pmask==0x83fe &&
        *(const UWORD *)(ULONG)loaded->ib_pdata==0x4202);
    for (i=0;i<3;++i) {
        CHECK(!rsrc_load(bad[i]));CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && tree==again);
    }
    compiled=*loaded;compiled.ib_pmask=(ULONG)mask;compiled.ib_pdata=(ULONG)bits;
    for (i=0;i<32;++i) { mask[i]=(i&1) ? 0xf3c0:0x83fe;bits[i]=(i&1) ? 0xa140:0x4202; }
    v_opnvwk(work_in,&handle,work_out);CHECK(handle>0);
    window=wind_create(NAME|CLOSER|MOVER,0,0,640,208);CHECK(window>0);
    CHECK(wind_open(window,0,24,640,208));
    for (i=0;i<8;++i) {
        icon.ob_x=57+(i&1);icon.ob_state=(i&2) ? SELECTED:0;
        icon.ob_spec=(ULONG)(i<4 ? &compiled:loaded);
        CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(&background,0,0,0,0,640,240));
        CHECK(objc_draw(&icon,0,0,i>=4 ? icon.ob_x+11:0,i>=4 ? 83:0,i>=4 ? 24:640,i>=4 ? 21:240));
        CHECK(wind_update(END_UPDATE));
        IconPhase=i+1;while (IconGo<IconPhase) ExecYield();
    }
    CHECK(wind_close(window));CHECK(wind_delete(window));v_clsvwk(handle);
    CHECK(rsrc_free());
}
static void colour_resource(void)
{
    static UWORD mask[32],selectedMask[32];
    static UBYTE normal[256],selected[256];
    static CICON form;
    static CICONBLK compiled;
    static OBJECT background={-1,-1,-1,G_BOX,LASTOB,0,0x1175,8,40,624,184};
    static OBJECT icon={-1,-1,-1,G_CICON,LASTOB,0,0,57,81,96,32};
    const char *bad[]={"D1:CILEN.RSC","D1:CITAB.RSC","D1:CIINDEX.RSC","D1:CIWIDTH.RSC",
        "D1:CIPLANE.RSC","D1:CICOUNT.RSC","D1:CICUT.RSC"};
    OBJECT *tree,*again;
    CICONBLK *loaded;
    WORD i,row,x,window,handle=1;
    CHECK(rsrc_load("D1:CICONS.RSC"));CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    CHECK(tree[1].ob_spec==tree[5].ob_spec);
    for (i=0;i<7;++i) {
        CHECK(!rsrc_load(bad[i]));CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && tree==again);
    }
    loaded=(CICONBLK *)(ULONG)tree[1].ob_spec;compiled=*loaded;
    form=*(CICON *)(ULONG)loaded->mainlist;
    CHECK(form.num_planes==4 && form.col_data>65535UL && form.sel_data && !form.next_res);
    CHECK(*(const UBYTE *)(ULONG)form.col_data==0x01 && *(const UBYTE *)(ULONG)form.sel_data==0xfe);
    CHECK(!((CICONBLK *)(ULONG)tree[3].ob_spec)->mainlist);
    form.col_data=(ULONG)normal;form.sel_data=(ULONG)selected;
    form.col_mask=(ULONG)mask;form.sel_mask=(ULONG)selectedMask;compiled.mainlist=(ULONG)&form;
    for (i=0;i<32;++i) { mask[i]=(i&1) ? 0xf3c0:0x83fe;selectedMask[i]=0x5aa5; }
    for (row=0;row<16;++row) for (x=0;x<32;x+=2) {
        UBYTE value=(((row+x)&15)<<4)|((row+x+1)&15);
        normal[row*16+x/2]=value;selected[row*16+x/2]=value^255;
    }
    v_opnvwk(work_in,&handle,work_out);CHECK(handle>0);
    window=wind_create(NAME|CLOSER|MOVER,0,0,640,208);CHECK(window>0);
    CHECK(wind_open(window,0,24,640,208));
    for (i=0;i<18;++i) {
        icon.ob_x=57+(i&1);icon.ob_state=(i&2) ? SELECTED:0;
        icon.ob_height=i>=16 ? 80:32;
        icon.ob_spec=i<4 ? (ULONG)&compiled:tree[1+(i-4)/4].ob_spec;
        CHECK(wind_update(BEG_UPDATE));CHECK(objc_draw(&background,0,0,0,0,640,240));
        CHECK(objc_draw(&icon,0,0,i>=4 && i<8 ? icon.ob_x+11:0,
            i>=4 && i<8 ? 83:0,i>=4 && i<8 ? 24:640,i>=4 && i<8 ? 21:240));
        CHECK(wind_update(END_UPDATE));
        IconPhase=i+9;while (IconGo<IconPhase) ExecYield();
    }
    CHECK(wind_close(window));CHECK(wind_delete(window));v_clsvwk(handle);
    /* Leave this resource to appl_exit to cover colour resource ownership. */
}
UWORD AESRun(void)
{
    OBJECT *tree,*again,*popup;
    BPTR lock,file;
    ULONG memory;
    WORD x,y,words[8];
    struct ExecAESContext *context;
    /* Mount/cache allocations persist until system shutdown. Warm them before
       measuring the resource/context lifetime. */
    file=Open("D1:DESKTOP.RSC",MODE_OLDFILE);
    CHECK(file!=0);CHECK(Seek(file,0,OFFSET_END)>=0);CHECK(Close(file));
    lock=Lock("D1:",SHARED_LOCK);CHECK(lock!=0);
    CHECK(Examine(lock,&info));CHECK(ExNext(lock,&info));UnLock(lock);
    CHECK(ExecDOSDetach()); memory=AvailMem(0);ResourceHeapWarm=memory;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    context=ExecAESContext();
    for (x=0;x<8;++x) context->deferredMessage[x]=123+x;
    context->messagePending=1;
    CHECK(evnt_mesag(words) && words[0]==123 && words[7]==130 && !context->messagePending);
    x=rsrc_load("D1:DESKTOP.RSC");ResourceStatus=ExecAESDiagnostic();ResourceError=IoErr();
    CHECK(x);if (!x) goto cleanup;
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&tree));
    CHECK(tree[0].ob_width==216 && tree[0].ob_height==144);
    CHECK(tree[1].ob_type==G_BUTTON && ((char *)tree[1].ob_spec)[0]=='F');
    CHECK(objc_offset(tree,4,&x,&y) && x==8 && y==32);
    CHECK(rsrc_gaddr(R_TREE,1,(void **)&popup) && popup[0].ob_width==112);
    CHECK(!rsrc_load("D1:BAD.RSC"));
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && again==tree);
    CHECK(!rsrc_load("D1:SHORT.RSC"));
    CHECK(rsrc_gaddr(R_TREE,0,(void **)&again) && again==tree);
    CHECK(!rsrc_gaddr(R_TREE,3,(void **)&again) && !again);
    CHECK(menu_ienable(popup,1,0) && popup[1].ob_state==DISABLED);
    CHECK(menu_ienable(popup,1,1) && popup[1].ob_state==0);
    CHECK(menu_tnormal(popup,1,0) && popup[1].ob_state==SELECTED);
    CHECK(menu_text(popup,1,"Launch") && ((char *)popup[1].ob_spec)[0]=='L');
    CHECK(rsrc_free()); CHECK(!rsrc_gaddr(R_TREE,0,(void **)&again));
    CHECK(rsrc_load("D1:DESKTOP.RSC"));
    lock=Lock("D1:",SHARED_LOCK); CHECK(lock!=0);
    CHECK(Examine(lock,&info)!=0 && info.fib_DirEntryType>0);
    CHECK(ExNext(lock,&info)!=0 && info.fib_FileName[0]!=0);
    UnLock(lock);
    file=Open("D1:DESKTOP.RSC",MODE_OLDFILE);CHECK(file!=0);
    CHECK(Seek(file,36,OFFSET_BEGINNING)==0);CHECK(Seek(file,0,OFFSET_CURRENT)==36);
    CHECK(Close(file));
    text_resource();editable_resource();icon_resource();colour_resource();
cleanup:
    CHECK(appl_exit());CHECK(ExecAESDetach());CHECK(ExecDOSDetach());
    ResourceHeapReturned=AvailMem(0);CHECK(ResourceHeapReturned==memory);
    return AESFailures;
}
