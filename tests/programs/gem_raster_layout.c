#include "../../examples/gem-raster/raster.h"
__attribute__((section("exec_layout"))) const UWORD RasterLayout[]={
    sizeof(struct RasterApp),offsetof(struct RasterApp,ready),offsetof(struct RasterApp,scrolls),
    offsetof(struct RasterApp,shifts),offsetof(struct RasterApp,roundtrips),offsetof(struct RasterApp,running),
    offsetof(struct RasterApp,left),offsetof(struct RasterApp,first),offsetof(struct RasterApp,work)
};
