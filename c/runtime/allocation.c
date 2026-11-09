/* SPDX-License-Identifier: MIT
 * Extracted from the Exec816 QED adapter. Each loaded image owns its list.
 * The prefix is the original, bank-contained AllocMem pointer.
 */
#include "internal.h"
#include <proto/exec.h>
#include <proto/dos.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

#ifdef EXEC_CRT_TEST
extern APTR ExecCRTTestAllocMem(ULONG,ULONG);
#define BACKING_ALLOC ExecCRTTestAllocMem
#else
#define BACKING_ALLOC AllocMem
#endif

static struct ExecCRuntimeAllocation *owned;
static struct ExecCRuntimeHeapStats totals;

void ExecCRuntimeHeapBegin(void)
{
    owned=NULL;
    memset(&totals,0,sizeof(totals));
    errno=0;
}

void *malloc(size_t bytes)
{
    struct ExecCRuntimeAllocation *block;
    ULONG backing;
    if (!bytes) return NULL;
    if ((ULONG)bytes>EXEC_CRT_MAX_ALLOCATION) {
        errno=ENOMEM;SetIoErr(ERROR_NO_FREE_STORE);return NULL;
    }
    backing=(ULONG)bytes+EXEC_CRT_ALLOCATION_PREFIX;
    block=BACKING_ALLOC(backing,MEMF_UPPER);
    if (!block) { errno=ENOMEM;SetIoErr(ERROR_NO_FREE_STORE);return NULL; }
    block->previous=NULL;block->next=owned;block->bytes=bytes;block->reserved=0;
    if (owned) owned->previous=block;
    owned=block;
    ++totals.blocks;totals.payload+=bytes;totals.backing+=backing;
    if (totals.backing>totals.peakBacking) totals.peakBacking=totals.backing;
    return block+1;
}

void free(void *pointer)
{
    struct ExecCRuntimeAllocation *block;
    ULONG bytes;
    if (!pointer) return;
    block=(struct ExecCRuntimeAllocation *)pointer-1;bytes=block->bytes;
    if (block->previous)
        ((struct ExecCRuntimeAllocation *)block->previous)->next=block->next;
    else owned=block->next;
    if (block->next)
        ((struct ExecCRuntimeAllocation *)block->next)->previous=block->previous;
    --totals.blocks;totals.payload-=bytes;totals.backing-=bytes+EXEC_CRT_ALLOCATION_PREFIX;
    FreeMem(block,bytes+EXEC_CRT_ALLOCATION_PREFIX);
}

void *calloc(size_t count,size_t bytes)
{
    void *pointer;
    if (!count || !bytes) return NULL;
    if ((ULONG)bytes>EXEC_CRT_MAX_ALLOCATION/(ULONG)count) {
        errno=ENOMEM;SetIoErr(ERROR_NO_FREE_STORE);return NULL;
    }
    pointer=malloc(count*bytes);
    if (pointer) memset(pointer,0,count*bytes);
    return pointer;
}

void *realloc(void *pointer,size_t bytes)
{
    void *replacement;
    ULONG old;
    if (!pointer) return malloc(bytes);
    if (!bytes) { free(pointer);return NULL; }
    old=((struct ExecCRuntimeAllocation *)pointer-1)->bytes;
    replacement=malloc(bytes);
    if (!replacement) return NULL;
    memcpy(replacement,pointer,bytes<old ? bytes:old);
    free(pointer);
    return replacement;
}

void ExecCRuntimeHeapSnapshot(struct ExecCRuntimeHeapStats *stats) { *stats=totals; }
void ExecCRuntimeHeapRelease(void)
{
    while (owned) free(owned+1);
}
