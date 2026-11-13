/* Exec-owned surfaces for the selected GEM4XE algorithms; no VRAM tags. */
#ifndef EXEC_GEM_RASTER_DRAWING_H
#define EXEC_GEM_RASTER_DRAWING_H
#include <exec/types.h>
#include <exec/display.h>
#include <gem.h>
#include "geometry.h"
struct GemRasterSurface { UBYTE *address; UWORD pitch,width,height; };
struct GemRasterCopy {
    struct GemRasterSurface source,destination;
    struct GemRasterRect rect;
    WORD mode;
};
struct ExecAESContext;
void ExecGemRasterCopy(struct ExecAESContext *context,WORD mode,const WORD *points,
    const MFDB *source,const MFDB *destination);
UWORD GemDrawingRasterBorrow(struct DisplayGrant *grant,const struct GemRasterCopy *copy,
    UBYTE *scratch);
#endif
