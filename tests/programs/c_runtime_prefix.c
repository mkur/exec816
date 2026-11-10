/* SPDX-License-Identifier: MIT: small raw/optimized compiler-facing probe. */
#include "internal.h"
#include <proto/exec.h>
#include <stdlib.h>
#include <string.h>
static int executions;
APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags) { return AllocMem(bytes,flags); }
int main(void)
{
    struct ExecCRuntimeAllocation *prefix;
    char *p,**argv;
    int argc;
    ExecCRuntimeHeapRelease();
    ExecCRuntimeHeapBegin();
    p=malloc(13);
    if (!p || ((ULONG)p&7)) return 1;
    prefix=(struct ExecCRuntimeAllocation *)p-1;
    if (prefix->bytes!=13 || prefix->previous || prefix->next || prefix->reserved ||
        (char *)(prefix+1)-(char *)prefix!=16) return 2;
    if (!ExecCRuntimeArguments("a \"\"","test",&argc,&argv) || argc!=3 ||
        strcmp(argv[1],"a") || *argv[2] || argv[3]) return 3;
    ExecCRuntimeHeapRelease();
    return -321-executions++;
}
