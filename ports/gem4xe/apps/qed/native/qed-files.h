/* SPDX-License-Identifier: MIT */
#ifndef QED_FILES_H
#define QED_FILES_H
#include "qed-runtime.h"
#include <proto/dos.h>
#include <exec816/c-runtime.h>
#define QED_FILE_SLOTS EXEC_CRT_FILE_SLOTS
struct QedFileInfo {
    LONG size,protection,kind;
    struct DateStamp date;
    UWORD sizeKnown,dateKnown;
};
LONG QedFileError(void);
UWORD QedFileCount(void);
int QedFileInfo(const char *path,struct QedFileInfo *info);
LONG Fopen(const char *path,WORD mode);
LONG Fcreate(const char *path,WORD attributes);
LONG QedFileExclusive(const char *path);
LONG QedFileCloseError(void);
LONG Fclose(WORD fd);
LONG Fread(WORD fd,LONG bytes,void *buffer);
LONG Fwrite(WORD fd,LONG bytes,const void *buffer);
LONG Fseek(LONG offset,WORD fd,WORD origin);
LONG Fdelete(const char *path);
LONG Frename(WORD zero,const char *before,const char *after);
#endif
