/* MIT. Ordinary resident C main, independent of the loadable APP runtime. */
#include <proto/exec.h>
#include <exec816/runtime.h>
static volatile ULONG computing;
int main(void)
{
    struct Task *owner=FindTask(NULL);
    UBYTE *block=AllocMem(37,MEMF_UPPER);
    UWORD i,j;
    if (!owner || !block) return 99;
    for (i=0;i<37;++i) block[i]=(UBYTE)(i^0x5a);
    for (i=0;i<128;++i) {
        for (j=0;j<64;++j) computing=computing*1664525UL+1013904223UL;
        ExecYield();
        if (FindTask(NULL)!=owner) return 98;
        for (j=0;j<37;++j) if (block[j]!=(UBYTE)(j^0x5a)) return 97;
    }
    FreeMem(block,37);
    return computing==1695850496UL ? -123:96;
}
