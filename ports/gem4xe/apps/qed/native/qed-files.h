/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef QED_FILES_H
#define QED_FILES_H
#include "qed-runtime.h"
#include <proto/dos.h>
#define QED_FILE_SLOTS 4
struct QedFileInfo {
    LONG size,protection,kind;
    struct DateStamp date;
    UWORD sizeKnown,dateKnown;
};
void QedFilesBegin(void);
LONG QedFilesCleanup(LONG cause);
LONG QedFileError(void);
UWORD QedFileCount(void);
int QedFileInfo(const char *path,struct QedFileInfo *info);
LONG Fopen(const char *path,WORD mode);
LONG Fcreate(const char *path,WORD attributes);
LONG Fclose(WORD fd);
LONG Fread(WORD fd,LONG bytes,void *buffer);
LONG Fwrite(WORD fd,LONG bytes,const void *buffer);
LONG Fseek(LONG offset,WORD fd,WORD origin);
LONG Fdelete(const char *path);
LONG Frename(WORD zero,const char *before,const char *after);
#endif
