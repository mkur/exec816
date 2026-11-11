/* Separate translation unit keeps exact call brackets in optimized fixtures. */
#include <exec/types.h>
extern volatile UWORD FramePoint;
void FrameCallBegin(void) { FramePoint=1; }
void FrameCallEnd(void) { FramePoint=2; }
void FrameRelease(void) { FramePoint=5; }
