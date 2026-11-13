#ifndef EXEC_GEM_RASTER_CLIENT_H
#define EXEC_GEM_RASTER_CLIENT_H
#include <gem.h>
struct ExecAESContext;
void ExecGemRasterCopy(struct ExecAESContext *context,WORD mode,const WORD *points,
    const MFDB *source,const MFDB *destination);
#endif
