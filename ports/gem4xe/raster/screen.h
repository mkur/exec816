/* GEM4XE rop_code recipes over Exec's admitted synchronous driver.
 * Included by the drawing adapter after its private owner/fence helpers.
 * GPL-2.0-or-later; see inputs.json. */
static UWORD raster_move(UWORD sx,UWORD sy,UWORD dx,UWORD dy,UWORD bytes,UWORD rows,UWORD code)
{
    UBYTE record[21];
    ULONG source=GemScreenRows[sy]+(sx>>1),destination=GemScreenRows[dy]+(dx>>1);
    UWORD pitch=320,step=1;
    if (destination>source) {
        source+=(ULONG)(rows-1)*320+bytes-1;
        destination+=(ULONG)(rows-1)*320+bytes-1;
        pitch=(UWORD)-320;step=255;
    }
    record[0]=(UBYTE)source;record[1]=(UBYTE)(source>>8);record[2]=(UBYTE)(source>>16);
    record[6]=(UBYTE)destination;record[7]=(UBYTE)(destination>>8);record[8]=(UBYTE)(destination>>16);
    record[3]=record[9]=(UBYTE)pitch;record[4]=record[10]=(UBYTE)(pitch>>8);
    record[5]=record[11]=(UBYTE)step;
    record[12]=(UBYTE)(bytes-1);record[13]=(UBYTE)((bytes-1)>>8);record[14]=(UBYTE)(rows-1);
    record[15]=(UBYTE)(code&1 ? 255:0);record[16]=(UBYTE)(code&2 ? 255:0);
    /* Establish every field, including unused pattern, zoom and collision. */
    record[17]=0;record[18]=0;record[19]=0;
    record[20]=(UBYTE)((code>>2)&7);
    return VbxeOwnerSubmit(&display,record,1);
}

static UWORD raster_logic(struct DisplayGrant *grant,const struct GemRasterCopy *p,UBYTE *scratch)
{
    const struct GemRasterRect *r=&p->rect;
    UWORD sx=r->sx,sy=r->sy,dx=r->dx,dy=r->dy,width=r->width,height=r->height;
    UWORD code=GemRasterRecipes[p->mode],inv=code>>5;
    UWORD l=sx&1,right=(sx+width)&1,bytes=(width-l-right)>>1;
    UWORD remaining=height,first,n,k,y,limit,status;
    limit=(UWORD)VBXE_LIST_WORK/(bytes*(inv ? 6:3)+(l+right)*3);
    if (limit>EXEC_VDI_STRIP_ROWS) limit=EXEC_VDI_STRIP_ROWS;
    while (remaining) {
        n=remaining<limit ? remaining:limit;
        first=dy>sy ? remaining-n:height-remaining;
        status=DisplayEnter(grant);
        if (status!=DISPLAY_OK) return status;
        pointer_erase(sx,sy+first,sx+width,sy+first+n);
        pointer_erase(dx,dy+first,dx+width,dy+first+n);
        status=fence_owner();
        for (k=0;k<n && !fault;++k) {
            y=first+k;
            if (l) {
                latch(VbxeOwnerRead(&display,GemScreenRows[sy+y]+(sx>>1),scratch+k*4,1));
                if (!fault) latch(VbxeOwnerRead(&display,GemScreenRows[dy+y]+(dx>>1),scratch+k*4+1,1));
            }
            if (right && !fault) {
                latch(VbxeOwnerRead(&display,GemScreenRows[sy+y]+((sx+width-1)>>1),scratch+k*4+2,1));
                if (!fault) latch(VbxeOwnerRead(&display,GemScreenRows[dy+y]+((dx+width-1)>>1),scratch+k*4+3,1));
            }
        }
        if (!fault && bytes) {
            if (inv==1) latch(raster_move(dx+l,dy+first,dx+l,dy+first,bytes,n,GemRasterRecipes[D_INVERT]));
            if (!fault) latch(raster_move(sx+l,sy+first,dx+l,dy+first,bytes,n,code));
            if (inv==2 && !fault) latch(raster_move(dx+l,dy+first,dx+l,dy+first,bytes,n,GemRasterRecipes[D_INVERT]));
        }
        for (k=0;k<n && !fault;++k) {
            y=first+k;
            if (l) {
                GemRasterMerge(scratch+k*4+1,scratch+k*4,1,1,1,p->mode);
                latch(VbxeOwnerWrite(&display,GemScreenRows[dy+y]+(dx>>1),scratch+k*4+1,1));
            }
            if (right && !fault) {
                GemRasterMerge(scratch+k*4+3,scratch+k*4+2,0,0,1,p->mode);
                latch(VbxeOwnerWrite(&display,GemScreenRows[dy+y]+((dx+width-1)>>1),scratch+k*4+3,1));
            }
        }
        status=borrow_leave(grant);
        if (status!=DISPLAY_OK) return status;
        remaining-=n;
    }
    return DISPLAY_OK;
}
