/* Included only in the emitted widget fixture's private adapter copy. */
extern volatile uint16_t WidgetPixelFailures;
static UWORD builderActive,builderFull,builderWork;
static UBYTE builderReadback[512];
static void builder_check(UWORD good) { if (!good) ++WidgetPixelFailures; }
static void BuilderListProbe(const UBYTE *p,UWORD count)
{
    UWORD i,bytes,rows;
    ULONG work=0;
    if (!builderActive) return;
    builder_check(count && count<=64);
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
