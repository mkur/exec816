/* Included only in the emitted widget fixture's private adapter copy. */
extern volatile uint16_t WidgetPixelFailures;
static UWORD builderActive,builderFull,builderWork,builderLists,builderFailAt,builderCase;
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
        builder_check(bytes<=512 && rows<=16);
        work+=(ULONG)bytes*rows*(p[20] ? 3 : 2);
    }
    builder_check(work<=8192);
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
