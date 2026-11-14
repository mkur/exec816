/* SPDX-License-Identifier: MIT */
#ifndef GEM_RASTER_SAMPLE_H
#define GEM_RASTER_SAMPLE_H
#include <gem.h>
struct RasterApp {
    WORD id,window,opened;
    volatile WORD ready;
    volatile ULONG scrolls,shifts,roundtrips;
    WORD running,left;
    UWORD first;
    WORD work[4],message[8],input[11],output[57],vdi;
    MFDB memory;
    WORD points[8];
    char label[16];
};
extern struct RasterApp GEMRaster;
#endif
