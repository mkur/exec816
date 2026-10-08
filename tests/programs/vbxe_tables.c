/* Load/address boundary probe for the generated read-only upper bank. */
#include <exec/types.h>
#include "gem-vbxe-tables.h"
volatile UWORD failures,completed;
static void check(UWORD good) { if (!good) ++failures; }
int main(void)
{
    UWORD width,rows,index;
    for (rows=1;rows<=16;rows++) for (width=1;width<=512;width++) {
        index=((rows-1)<<9)|(width-1);
        check(GemWork2[index]==(ULONG)rows*width*2);
        check(GemWork3[index]==(ULONG)rows*width*3);
    }
    for (width=1;width<=512;width++) {
        rows=GemRowLimit2[width-1];
        check(rows<=16 && (ULONG)rows*width*2<=8192);
        rows=GemRowLimit3[width-1];
        check(rows<=16 && (ULONG)rows*width*3<=8192);
    }
    for (rows=0;rows<=16;rows++) {
        check(GemStep320[rows]==rows*320);
        check(GemStep640[rows]==rows*640);
        check(GemStep1024[rows]==rows*1024);
        check(GemStep1280[rows]==rows*1280);
    }
    for (rows=0;rows<256;rows++) check(GemScreenRows[rows]==(ULONG)rows*320);
    for (rows=0;rows<=64;rows++) check(GemRecordOffsets[rows]==rows*21);
    for (rows=0;rows<=1024;rows++) {
        width=GemGlyphCapacity96[rows];
        check(width*96<=rows*8 && (width==64 || (width+1)*96>rows*8));
        width=GemGlyphCapacity120[rows];
        check(width*120<=rows*8 && (width==64 || (width+1)*120>rows*8));
    }
    completed=1;
    return failures;
}
