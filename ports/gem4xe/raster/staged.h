/* Different-parity screen S_ONLY: blit, mapped native shift, masked publish.
 * Included by the drawing adapter; source/output slots share one mapped page.
 * GPL-2.0-or-later; the shifter is reproduced from the pinned GEM4XE input. */
#if DESKTOP_RASTER_SCRATCH_BYTES != 16384UL
#error Mapped raster layout requires sixteen 1024-byte row slots
#endif
struct RasterMappedShift { UWORD bytes,rows,right; };

static void raster_shift_page(UBYTE *window,void *context)
{
    const struct RasterMappedShift *p=context;
    UWORD row;
    UBYTE *source=window,*destination=window+512;
    for (row=0;row<p->rows;++row) {
        /* Source and output are disjoint. A final spare source byte stays
         * inside its private half-slot; that nibble is excluded at publish. */
        if (p->right) {
            destination[0]=source[0]>>4;
            GemRasterShift(destination+1,source,p->bytes-1);
        } else GemRasterShift(destination,source,p->bytes);
        source+=1024;destination+=1024;
    }
}

static UWORD raster_staged(struct DisplayGrant *grant,const struct GemRasterCopy *p)
{
    const struct GemRasterRect *r=&p->rect;
    UWORD sx=r->sx,sy=r->sy,dx=r->dx,dy=r->dy,width=r->width;
    UWORD sn=((sx&1)+width+1)>>1,dn=((dx&1)+width+1)>>1;
    UWORD l=dx&1,right=(dx+width)&1,bytes=dn-l-right;
    UWORD remaining=r->height,first,n,row,limit,status;
    struct RasterMappedShift shift;
    ULONG output=DESKTOP_RASTER_SCRATCH_BASE+512,destination;
    /* Source blit: 2*sn, native shift: <=3*dn, publish: 2*dn+3/edge.
     * Bound the entire physical unit, not just each individual BCB list. */
    limit=(UWORD)VBXE_LIST_WORK/(sn*2+dn*5+(l+right)*3);
    if (limit>EXEC_VDI_STRIP_ROWS) limit=EXEC_VDI_STRIP_ROWS;
    shift.bytes=dn;shift.right=dx&1;
    while (remaining) {
        n=remaining<limit ? remaining:limit;
        first=dy>sy ? remaining-n:r->height-remaining;
        status=DisplayEnter(grant);
        if (status!=DISPLAY_OK) return status;
        pointer_erase(sx,sy+first,sx+width,sy+first+n);
        pointer_erase(dx,dy+first,dx+width,dy+first+n);
        status=fence_owner();
        /* Capture the complete band before any destination write, including
         * horizontal overlap. Higher destination rows consume bands bottom up. */
        if (status==DISPLAY_OK) {
            blit_mask(GemScreenRows[sy+first]+(sx>>1),320,
                DESKTOP_RASTER_SCRATCH_BASE,1024,sn,n,255,0,0);
            status=fence_owner();
        }
        for (row=0;row<n && status==DISPLAY_OK;row+=4) {
            shift.rows=n-row<4 ? n-row:4;
            status=VbxeOwnerMapPage(&display,
                DESKTOP_RASTER_SCRATCH_BASE+((ULONG)row<<10),raster_shift_page,&shift);
        }
        latch(status);
        if (!fault) {
            destination=GemScreenRows[dy+first]+(dx>>1);
            if (l) {
                blit_and(destination,320,1,n,0xf0);
                blit_mask(output,1024,destination,320,1,n,0x0f,0,3);
            }
            if (bytes) blit_mask(output+l,1024,destination+l,320,bytes,n,255,0,0);
            if (right) {
                blit_and(destination+dn-1,320,1,n,0x0f);
                blit_mask(output+dn-1,1024,destination+dn-1,320,1,n,0xf0,0,3);
            }
        }
        status=borrow_leave(grant);
        if (status!=DISPLAY_OK) return status;
        remaining-=n;
    }
    return DISPLAY_OK;
}
