/* SPDX-License-Identifier: MIT
 * Per-image ownership. The header is the exact original AllocMem pointer.
 */
#include "qed-runtime.h"
#include <proto/dos.h>
#include <stdlib.h>
#include <string.h>

struct Allocation {
    struct Allocation *previous,*next;
    ULONG bytes;
};
static struct Allocation *owned;
static struct QedHeapStats totals;

void *malloc(size_t bytes)
{
    struct Allocation *block;
    ULONG backing;
    if (!bytes || bytes>65536UL-sizeof(*block)) return NULL;
    backing=(ULONG)bytes+sizeof(*block);
    block=AllocMem(backing,MEMF_UPPER);
    if (!block) { SetIoErr(ERROR_NO_FREE_STORE);return NULL; }
    block->previous=NULL;block->next=owned;block->bytes=bytes;
    if (owned) owned->previous=block;
    owned=block;
    ++totals.blocks;totals.payload+=bytes;totals.backing+=backing;
    if (totals.backing>totals.peakBacking) totals.peakBacking=totals.backing;
    return block+1;
}

void free(void *pointer)
{
    struct Allocation *block;
    ULONG bytes;
    if (!pointer) return;
    block=(struct Allocation *)pointer-1;bytes=block->bytes;
    if (block->previous) block->previous->next=block->next;
    else owned=block->next;
    if (block->next) block->next->previous=block->previous;
    --totals.blocks;totals.payload-=bytes;totals.backing-=bytes+sizeof(*block);
    FreeMem(block,bytes+sizeof(*block));
}

void *calloc(size_t count,size_t bytes)
{
    void *pointer;
    if (!count || !bytes || bytes>(size_t)-1/count) return NULL;
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
    old=((struct Allocation *)pointer-1)->bytes;
    replacement=malloc(bytes);
    if (!replacement) return NULL;
    memcpy(replacement,pointer,bytes<old ? bytes:old);
    free(pointer);
    return replacement;
}

LONG Malloc(LONG bytes)
{
    ULONG largest;
    if (bytes==-1) {
        largest=AvailMem(MEMF_UPPER|MEMF_LARGEST);
        return largest>sizeof(struct Allocation) ? largest-sizeof(struct Allocation):0;
    }
    return bytes>0 && (ULONG)(size_t)bytes==(ULONG)bytes ? (LONG)malloc((size_t)bytes):0;
}

LONG Mfree(void *pointer) { free(pointer);return 0; }
void QedHeapSnapshot(struct QedHeapStats *stats) { *stats=totals; }
void QedHeapCleanup(void)
{
    while (owned) free(owned+1);
}
