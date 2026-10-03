/* Benchmark-only addition to a generated copy of vbxe.c. This is deliberately
 * outside the production driver/API. The larger list bypasses only its normal
 * work quantum; admission, geometry, upload, waits and recovery remain checked.
 * Fixed console geometry: packed 640x240 screen, upward eight-pixel scroll.
 */
UWORD BenchmarkRectangleScroll(struct VbxeDisplay *d,const struct VbxeCopy *c)
{
    ULONG source,destination,bottom;
    UWORD bytes,i,status=check(d);
    UBYTE records[42];
    if (status!=DISPLAY_OK) return status;
    if (!extent(0,c,sizeof(*c))) return DISPLAY_BAD_ARGUMENT;
    if (c->source.offset || c->destination.offset ||
        c->source.pitch!=320 || c->destination.pitch!=320 ||
        c->source.width!=640 || c->destination.width!=640 ||
        c->source.height!=240 || c->destination.height!=240 ||
        c->sourceX!=c->destinationX || c->sourceX>640 ||
        (c->sourceX|c->width)&1 || !c->width || c->width>640-c->sourceX ||
        c->destinationY>232 || c->sourceY!=c->destinationY+8 ||
        !c->height || c->height>232-c->destinationY)
        return DISPLAY_BAD_ARGUMENT;
    bytes=c->width/2;
    source=(ULONG)c->sourceY*320+c->sourceX/2;
    destination=(ULONG)c->destinationY*320+c->destinationX/2;
    bottom=destination+(ULONG)c->height*320;
    if (!VbxeBlitExtent(source,320,bytes,c->height) ||
        !VbxeBlitExtent(destination,320,bytes,c->height) ||
        !VbxeBlitExtent(bottom,320,bytes,8)) return DISPLAY_BAD_ARGUMENT;
    for (i=0;i<42;i++) records[i]=0;
    word(records,(UWORD)source); records[2]=(UBYTE)(source>>16);
    word(records+3,320); records[5]=1;
    word(records+6,(UWORD)destination); records[8]=(UBYTE)(destination>>16);
    word(records+9,320); records[11]=1;
    word(records+12,bytes-1); records[14]=(UBYTE)(c->height-1);
    records[15]=255;
    /* Second record reads an arbitrary valid source with AND=0, XOR=0. */
    records[26]=1;
    word(records+27,(UWORD)bottom); records[29]=(UBYTE)(bottom>>16);
    word(records+30,320); records[32]=1;
    word(records+33,bytes-1); records[35]=7;
    return submit(d,records,2);
}
