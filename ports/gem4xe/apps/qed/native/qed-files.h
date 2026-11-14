/* SPDX-License-Identifier: MIT */
#ifndef QED_FILES_H
#define QED_FILES_H
#include "qed-runtime.h"
#include <proto/dos.h>
#include <exec816/c-runtime.h>
#include <compat/gemdos.h>
#define QED_FILE_SLOTS EXEC_CRT_FILE_SLOTS
struct QedFileInfo {
    LONG size,protection,kind;
    struct DateStamp date;
    UWORD sizeKnown,dateKnown;
};
LONG QedFileError(void);
UWORD QedFileCount(void);
int QedFileInfo(const char *path,struct QedFileInfo *info);
LONG QedFileExclusive(const char *path);
LONG QedFileCloseError(void);
#endif
