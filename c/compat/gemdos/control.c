/* SPDX-License-Identifier: MIT. The admitted FSTAT size/type information subset. */
#include "gemdos-internal.h"
#include <proto/dos.h>
#include <stdlib.h>
#include <string.h>

LONG Fcntl(WORD fd,LONG argument,WORD command)
{
    struct FileInfoBlock *info;
    XATTR result;
    LONG error;
    if (command!=FSTAT)
        return ExecGemdosResult(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN));
    info=malloc(sizeof(*info));
    if (!info)
        return ExecGemdosResult(ExecCRuntimeFail(ERROR_NO_FREE_STORE));
    if (ExecCRuntimeExamineFH(fd,info)<0) {
        error=ExecCRuntimeFileError();
        free(info);
        return ExecGemdosResult(ExecCRuntimeFail(error));
    }
    if (!(info->fib_InfoFlags&FIB_SIZE_EXACT) || info->fib_Size<0 ||
        info->fib_DirEntryType>=0) {
        free(info);
        return ExecGemdosResult(ExecCRuntimeFail(ERROR_ACTION_NOT_KNOWN));
    }
    memset(&result,0,sizeof(result));
    result.size=info->fib_Size;result.mode=GEMDOS_S_IFREG;
    free(info);
    memcpy((void *)(ULONG)argument,&result,sizeof(result));
    return 0;
}
