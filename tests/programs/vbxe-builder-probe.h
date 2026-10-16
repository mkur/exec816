/* Included only in the emitted widget fixture's private adapter copy. */
extern volatile uint16_t WidgetPixelFailures;
static UWORD builderActive,builderFull,builderWork,builderLists,builderFailAt,builderCase;
static UWORD builderFirst,builderRows,builderParity,builderRoute;
static UBYTE builderReadback[512];
static void builder_check(UWORD good) { if (!good) ++WidgetPixelFailures; }
static void BuilderListProbe(const UBYTE *p,UWORD count)
{
    UWORD i,bytes,rows;
    ULONG work=0;
    if (!builderActive) return;
    ++builderLists;
    builder_check(count && count<=64);
    if (builderCase==9 && builderLists==1)
        builder_check(count==64 && p[20]==0 && p[63*21+20]==6);
    if (builderCase==10 && builderLists==1)
        builder_check(count==2 && p[20]==0 && p[41]==6);
    if (count==64) builderFull=1;
    for (i=0;i<count;i++,p+=21) {
        bytes=((UWORD)p[12]|((UWORD)p[13]<<8))+1;
        rows=(UWORD)p[14]+1;
        builder_check(bytes<=512 && rows<=256);
        if ((builderCase>=200 && builderCase<272) || (builderCase>=300 && builderCase<372)) {
            builder_check(count==3 && p[20]==6 && rows==builderRows);
            builder_check(bytes==(builderParity ? 5 : 4));
        }
        work+=(ULONG)bytes*rows*(p[20] ? 3 : 2);
    }
    builder_check(work<=8192);
    builder_check(work==commandWork);
    if (work==8192) builderWork=1;
}
static UWORD BuilderSubmit(const UBYTE *p,UWORD count)
{
    BuilderListProbe(p,count);
    if (builderActive && builderFailAt && builderLists==builderFailAt)
        return DISPLAY_DEVICE_FAULT;
    return VbxeOwnerSubmit(&display,p,count);
}
void BuilderProbe(void)
{
    static const UWORD widths[]={1,170,171,256,257,273,274,320,455,456,512};
    static const UWORD strides[]={320,640,1024,1280,317};
    UWORD i,j,y,width,limit,value;
    ULONG address;
    builderActive=1;
    /* Observe table loads through emitted C, including last/row-boundary
     * entries. Arithmetic here is an oracle, never production construction. */
    for (y=1;y<=16;y++) for (i=1;i<=512;i++) {
        j=((y-1)<<9)|(i-1);
        builder_check(GemWork2[j]==(ULONG)y*i*2);
        builder_check(GemWork3[j]==(ULONG)y*i*3);
    }
    for (i=1;i<=512;i++) {
        limit=GemRowLimit2[i-1];
        builder_check(limit<=16 && (ULONG)limit*i*2<=8192 &&
            (limit==16 || (ULONG)(limit+1)*i*2>8192));
        limit=GemRowLimit3[i-1];
        builder_check(limit<=16 && (ULONG)limit*i*3<=8192 &&
            (limit==16 || (ULONG)(limit+1)*i*3>8192));
    }
    /* Full-height private geometry and exact row-limit transitions. Reads
     * check both the written rectangle and its untouched row suffix. */
    blit_fill(0x40000UL,512,512,256,0);
    for (i=0;i<11;i++) {
        address=0x40000UL+(ULONG)i*17*512;
        blit_fill(address,512,widths[i],17,(UBYTE)(i+1));
        blit_xor(address,512,widths[i],17,255);
    }
    blit_run();
    for (y=0;y<256;y++) {
        builder_check(VbxeOwnerRead(&display,0x40000UL+(ULONG)y*512,
                                    builderReadback,512)==DISPLAY_OK);
        i=y/17;width=i<11 ? widths[i] : 0;
        for (j=0;j<512;j++) {
            value=j<width ? ((i+1)^255) : 0;
            builder_check(builderReadback[j]==value);
        }
    }
    /* Record-capacity flush, exact work-capacity flush, then each supported
     * stride with a tail chunk. A final drain also resets the write cursor. */
    for (i=0;i<65;i++) blit_fill(0x60000UL+i,128,1,1,(UBYTE)i);
    blit_run();
    builder_check(VbxeOwnerRead(&display,0x60000UL,builderReadback,65)==DISPLAY_OK);
    for (i=0;i<65;i++) builder_check(builderReadback[i]==i);
    blit_fill(0x60000UL,512,512,8,51);
    blit_fill(0x61000UL,512,1,1,68);
    blit_run();
    for (i=0;i<5;i++) {
        blit_fill(0x60000UL,strides[i],1,17,(UBYTE)(85+i));
        blit_run();
        for (y=0;y<17;y++) {
            builder_check(VbxeOwnerRead(&display,0x60000UL+(ULONG)y*strides[i],
                                        builderReadback,1)==DISPLAY_OK);
            builder_check(builderReadback[0]==85+i);
        }
    }
    builder_check(builderFull && builderWork && !fault);
    builderActive=0;
}

extern void GemWidgetText(WORD,WORD,const WORD *,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
static WORD builderGlyphs[65];
extern void vbxe_widget_text_run(WORD,WORD,const WORD *,UWORD,WORD,UWORD,UWORD);
static void builder_partial(void)
{
    UWORD i,index=builderCase>=300 ? builderCase-300 : builderCase>=200 ? builderCase-200 : 0;
    WORD x=16+(index%8)*72+builderParity,y=8+(index/8)*24;
    builderGlyphs[0]='A';builderGlyphs[1]=' ';builderGlyphs[2]='g';builderGlyphs[3]='W';
    if (builderCase==100 || builderCase==102)
        for (i=0;i<63;i++) blit_fill(0x60000UL+i,128,1,1,(UBYTE)i);
    if (builderCase==101) blit_fill(0x60000UL,500,500,8,51);
    if (builderCase==103) {
        for (i=0;i<64;i++) blit_fill(0x60000UL+i,128,1,1,(UBYTE)i);
        for (i=0;i<4;i++) builderGlyphs[i]=' ';
    }
    if (builderRoute)
        GemWidgetText(x,y,builderGlyphs,4,2,0,y+builderFirst,640,y+builderFirst+builderRows);
    else
        vbxe_widget_text_run(x,y+builderFirst,builderGlyphs,4,2,builderFirst,builderRows);
    if (builderCase==103) builder_check(!builderLists && commandCount==64);
}
void BuilderPartialTests(UWORD routed)
{
    UWORD first,rows,parity,index=0,y;
    builderRoute=routed;builderRows=1;builderFirst=7;builderParity=1;
    for (builderCase=100;builderCase<=103;builderCase++) {
        if (builderCase==102) continue; /* Failure is checked after the pixel gate. */
        builderLists=0;builderActive=1;
        builder_check(GemDrawingBatch(0,8,640,16,builder_partial)==DISPLAY_OK);
        builder_check(builderLists==(builderCase==100 ? 2 : 1));
        builderActive=0;
    }
    builder_check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
    for (first=0;first<8;first++) for (rows=1;rows<=8-first;rows++) for (parity=0;parity<2;parity++) {
        builderFirst=first;builderRows=rows;builderParity=parity;
        builderCase=(routed ? 300 : 200)+index;builderLists=0;builderActive=1;y=8+(index/8)*24;
        builder_check(GemDrawingBatch(0,y,640,y+8,builder_partial)==DISPLAY_OK);
        builder_check(builderLists==1);
        builderActive=0;++index;
    }
}
static void builder_clip_edge(void)
{
    UWORD i=builderCase-400,k,count=4,pen=2;
    WORD x=16+(i%8)*72+(i&1),y=224+(i/8)*8;
    WORD left=x,right=x+32,top=y+2,bottom=y+6;
    if (i<4) { left=x+2;right=x+(i<2 ? 30 : 6);if (i>=2) count=1; }
    if (i==4 || i==5) pen=0;
    if (i==8 || i==9) right=left;
    if (i==10 || i==11) bottom=top;
    if (i==12 || i==13) { x=i==12 ? -3 : 638;left=0;right=640; }
    if (i>=14) { top=y+7;bottom=y+8; }
    for (k=0;k<4;k++) builderGlyphs[k]=i==6 || i==7 ? ' ' : 'A';
    GemWidgetText(x,y,builderGlyphs,count,pen,left,top,right,bottom);
}
void BuilderClipEdges(void)
{
    UWORD y;
    for (builderCase=400;builderCase<416;builderCase++) {
        y=224+((builderCase-400)/8)*8;builderLists=0;builderActive=1;
        builder_check(GemDrawingBatch(0,y,640,y+8,builder_clip_edge)==DISPLAY_OK);
        builder_check(builderLists==((builderCase>=406 && builderCase<=411) ? 0 : 1));
        builderActive=0;
    }
}
void BuilderPartialFault(void)
{
    WORD workout[57];
    builderFirst=3;builderRows=4;builderParity=1;
    builderCase=102;builderLists=0;builderActive=1;builderFailAt=2;
    builder_check(GemDrawingBatch(0,8,640,16,builder_partial)==DISPLAY_DEVICE_FAULT);
    builder_check(builderLists==2 && fault==DISPLAY_DEVICE_FAULT && !commandCount);
    builder_partial();
    builder_check(builderLists==2 && !commandCount);
    builderActive=builderFailAt=0;
    builder_check(GemDrawingClose()==DISPLAY_DEVICE_FAULT);
    builder_check(GemDrawingOpen(workout)==DISPLAY_OK);
    builder_check(!fault && !commandCount && commandNext==commands);
}
static void builder_glyphs(void)
{
    UWORD i,count=builderCase==0 ? 63 : builderCase==1 ? 64 : 65;
    WORD x=builderCase==3 || builderCase==6 || builderCase==8 || builderCase==10 ||
            builderCase==12 || builderCase==1 || builderCase==5 ? 9 : 8;
    WORD y=builderCase==14 ? -3 : builderCase==15 ? 237 : 8+(builderCase<<4);
    if (builderCase==13) x=-3;
    for (i=0;i<65;i++) builderGlyphs[i]=builderCase==4 || (builderCase==5 && i%3==0) ? ' ' : 'A';
    if (builderCase==9)
        for (i=0;i<63;i++) blit_fill(0x60000UL+i,128,1,1,(UBYTE)i);
    if (builderCase==10) blit_fill(0x60000UL,500,500,8,51);
    if (builderCase==11) *vram_win(0x50000UL)=0xa5;
    GemWidgetText(x,y,builderGlyphs,count,builderCase==8 ? 0 : 2,
        builderCase==6 ? 12 : 0,builderCase==7 ? y+2 : builderCase==14 ? 0 : y,
        builderCase==6 ? 519 : 640,builderCase==7 ? y+6 : builderCase==15 ? 240 : y+8);
}
void BuilderRunTests(void)
{
    UWORD y;
    for (builderCase=0;builderCase<16;builderCase++) {
        y=builderCase==14 ? 0 : builderCase==15 ? 232 : 8+(builderCase<<4);
        builderLists=0;builderActive=1;
        if (builderCase==12) builder_check(GemDrawingPointer(100,y,1)==DISPLAY_OK);
        builder_check(GemDrawingBatch(0,y,640,y+8,builder_glyphs)==DISPLAY_OK);
        if (builderCase==12) builder_check(GemDrawingPointer(0,0,0)==DISPLAY_OK);
        if (builderCase==0 || builderCase==1 || builderCase==5) builder_check(builderLists==1);
        if (builderCase==2 || builderCase==3 || builderCase==9 || builderCase==10 || builderCase==11 || builderCase==12)
            builder_check(builderLists==2);
        if (builderCase==4) builder_check(!builderLists);
        builderActive=0;
    }
}
void BuilderFaultProbe(void)
{
    WORD workout[57];
    UWORD i;
    builderCase=99;builderLists=0;builderActive=1;builderFailAt=2;
    for (i=0;i<65;i++) builderGlyphs[i]='A';
    blit_fill(0x60000UL,512,512,8,0);
    GemWidgetText(8,8,builderGlyphs,65,2,0,0,640,240);
    builder_check(builderLists==2 && fault==DISPLAY_DEVICE_FAULT && commandCount==0);
    blit_fill(0x60000UL,512,1,1,0);
    builder_check(builderLists==2 && !commandCount && GemDrawingFence()==DISPLAY_DEVICE_FAULT);
    builderActive=builderFailAt=0;
    builder_check(GemDrawingClose()==DISPLAY_DEVICE_FAULT);
    builder_check(GemDrawingOpen(workout)==DISPLAY_OK);
    builder_check(!fault && !commandCount && commandNext==commands);
}

/* Exercise the fixed-operation encoder directly under owner admission, with
 * no arbitrary callback claiming a taller drawing rectangle. */
static const UWORD solidCases[][5]={
    {20,20,120,70,4},{21,20,121,70,4},
    {20,20,21,52,0},{21,20,22,52,2},{20,20,22,53,1},
    {0,0,256,31,8},{0,0,256,32,0},{0,0,256,33,2},
    {1,10,101,84,6},{1,10,101,85,6},{0,0,640,240,8},
    {639,0,640,240,0},{0,239,640,240,1},{17,17,624,49,5}
};
void BuilderSolidProbe(UWORD index)
{
    const UWORD *p=solidCases[index];
    UWORD width=p[2]-p[0],rows=p[3]-p[1],edge=(p[0]&1)+(p[2]&1);
    UWORD bytes=(width-edge)>>1,cost=bytes*2+edge*6,limit=8192/cost;
    if (limit>240) limit=240;
    builder_check(render_enter()==DISPLAY_OK);
    builderCase=30+index;builderLists=0;builderActive=1;
    builder_check(GemSolidRows(p[0],p[2])==limit);
    GemSolidFill(p[0],p[1],p[2],p[3],p[4]);
    builder_check(fence_owner()==DISPLAY_OK);
    builder_check(builderLists==(rows+limit-1)/limit);
    builderActive=0;render_exit(DISPLAY_OK);
}
void BuilderSolidFault(void)
{
    WORD workout[57];
    builder_check(render_enter()==DISPLAY_OK);
    builderCase=99;builderLists=0;builderActive=1;builderFailAt=2;
    GemSolidFill(1,0,639,240,2);
    builder_check(builderLists==2 && fault==DISPLAY_DEVICE_FAULT && !commandCount);
    GemSolidFill(0,0,640,240,0);
    builder_check(builderLists==2 && !commandCount && fence_owner()==DISPLAY_DEVICE_FAULT);
    builderActive=builderFailAt=0;render_exit(DISPLAY_DEVICE_FAULT);
    builder_check(GemDrawingClose()==DISPLAY_DEVICE_FAULT);
    builder_check(GemDrawingOpen(workout)==DISPLAY_OK);
}
