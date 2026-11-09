/* SPDX-License-Identifier: MIT */
#include "internal.h"
#include <proto/exec.h>
#include <exec816/runtime.h>
#include <proto/dos.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static UWORD executions,failNext;
APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags)
{
    APTR block;
    if (failNext) { failNext=0;return NULL; }
    block=AllocMem(bytes,flags);
    if (block) memset(block,0xa5,(size_t)(bytes>65535UL ? 65535UL:bytes));
    return block;
}

static int arguments(void)
{
    char **argv;
    char tail[257],name[256];
    int argc;
    unsigned int i;
    if (!ExecCRuntimeArguments("  a\tb\" c\" \"\" x\\y  ","probe",&argc,&argv)) return 1;
    if (argc!=5 || strcmp(argv[0],"probe") || strcmp(argv[1],"a") ||
        strcmp(argv[2],"b c") || strcmp(argv[3],"") || strcmp(argv[4],"x\\y") || argv[5]) return 2;
    free(argv);
    if (!ExecCRuntimeArguments("",NULL,&argc,&argv) || argc!=1 || *argv[0] || argv[1]) return 3;
    free(argv);
    if (ExecCRuntimeArguments("a\"b","probe",&argc,&argv) || errno!=EINVAL || argc || argv) return 4;
    for (i=0;i<255;++i) { tail[i]=i&1 ? ' ':'a';name[i]='n'; }
    tail[255]=name[255]=0;
    if (!ExecCRuntimeArguments(tail,name,&argc,&argv) || argc!=129 || argv[129] || strlen(argv[0])!=255) return 5;
    for (i=1;i<129;++i) if (strcmp(argv[i],"a")) return 6;
    free(argv);
    tail[255]='a';tail[256]=0;
    if (ExecCRuntimeArguments(tail,"probe",&argc,&argv) || errno!=E2BIG) return 7;
    failNext=1;
    if (ExecCRuntimeArguments("one two","probe",&argc,&argv) || errno!=ENOMEM || argc || argv) return 8;
    return 0;
}

int main(void)
{
    struct ExecCRuntimeHeapStats stats;
    char *blocks[8],*p,*q;
    ULONG address;
    unsigned int i,j;
    int result;
    ++executions;
    if (executions>2) return 101;
    ExecCRuntimeHeapSnapshot(&stats);
    if (stats.blocks || stats.backing) return 102;
    ExecCRuntimeHeapBegin();
    ExecCRuntimeHeapSnapshot(&stats);
    if (errno || stats.peakBacking) return 103;
    errno=91;
    if (malloc(0) || calloc(0,1) || calloc(1,0) || realloc(NULL,0) || errno!=91) return 104;
    free(NULL);
    for (i=0;i<8;++i) {
        blocks[i]=malloc(i+1);
        if (!blocks[i] || ((ULONG)blocks[i]&7)) return 105;
        memset(blocks[i],0x30+i,i+1);
    }
    for (i=0;i<8;i+=2) free(blocks[i]);
    for (i=1;i<8;i+=2) free(blocks[i]);
    p=malloc(65520U);
    if (!p) return 106;
    address=(ULONG)(p-EXEC_CRT_ALLOCATION_PREFIX);
    if ((address&65535UL) || ((ULONG)(p+65519)>>16)!=(address>>16)) return 107;
    p[0]=1;p[65519]=2;
    free(p);
    if (malloc(65521U) || errno!=ENOMEM || calloc(32768U,2) || calloc(65535U,65535U)) return 108;
    p=calloc(17,3);
    if (!p) return 109;
    for (i=0;i<51;++i) if (p[i]) return 110;
    for (i=0;i<51;++i) p[i]=(char)i;
    failNext=1;q=realloc(p,100);
    if (q || errno!=ENOMEM) return 111;
    for (i=0;i<51;++i) if (p[i]!=(char)i) return 112;
    q=realloc(p,100);if (!q) return 113;p=q;
    for (i=0;i<51;++i) if (p[i]!=(char)i) return 114;
    q=realloc(p,13);if (!q) return 115;p=q;
    for (i=0;i<13;++i) if (p[i]!=(char)i) return 116;
    if (realloc(p,0)) return 117;
    if ((result=arguments())) return 120+result;
    /* Instances overlap with private errno, ownership and application globals. */
    p=malloc(83);if (!p) return 131;
    memset(p,executions,83);errno=91;
    for (j=0;j<8;++j) {
        ExecYield();
        if (errno!=91) return 132;
        for (i=0;i<83;++i) if (p[i]!=executions) return 133;
    }
    if (!malloc(9) || !malloc(27)) return 134;
    ExecCRuntimeHeapSnapshot(&stats);
    if (stats.blocks!=3 || stats.payload!=119 || stats.backing!=167 || stats.peakBacking!=65536UL) return 135;
    ExecCRuntimeHeapRelease();
    ExecCRuntimeHeapSnapshot(&stats);
    if (stats.blocks || stats.payload || stats.backing) return 136;
    errno=EIO;
    return -320-executions;
}
