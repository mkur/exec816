/* SPDX-License-Identifier: MIT. Thin GEMDOS compatibility over the common CRT. */
#include "qed-files.h"
#include "gemdos-internal.h"
#include <calypsi/stubs.h>
#include <stdio.h>
#include <fcntl.h>
#include <stdlib.h>
LONG QedFileExclusive(const char *path)
{ return ExecGemdosResult(_Stub_open(path,O_WRONLY|O_CREAT|O_EXCL)); }
LONG QedFileCloseError(void) { return ExecCRuntimeCloseError(); }
LONG QedFileError(void) { return ExecCRuntimeFileError(); }
UWORD QedFileCount(void) { return ExecCRuntimeFileCount(); }
int QedFileInfo(const char *path,struct QedFileInfo *info)
{
    BPTR lock=Lock(path,SHARED_LOCK);
    struct FileInfoBlock *fib;
    LONG error;
    if (!lock) { ExecCRuntimeFail(IoErr());return 0; }
    fib=malloc(sizeof(*fib));
    if (!fib) { UnLock(lock);ExecCRuntimeFail(ERROR_NO_FREE_STORE);return 0; }
    if (!ExamineExact(lock,fib)) {
        error=IoErr();free(fib);UnLock(lock);ExecCRuntimeFail(error);return 0;
    }
    info->size=fib->fib_Size;info->protection=fib->fib_Protection;
    info->kind=fib->fib_DirEntryType;info->date=fib->fib_Date;
    info->sizeKnown=(fib->fib_InfoFlags&FIB_SIZE_EXACT)!=0;
    info->dateKnown=(fib->fib_Date.ds_Days || fib->fib_Date.ds_Minute || fib->fib_Date.ds_Tick) &&
        fib->fib_Date.ds_Days>=0 && fib->fib_Date.ds_Minute>=0 && fib->fib_Date.ds_Minute<1440 &&
        fib->fib_Date.ds_Tick>=0 && fib->fib_Date.ds_Tick<3000;
    free(fib);UnLock(lock);return 1;
}
