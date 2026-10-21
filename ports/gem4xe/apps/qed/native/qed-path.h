/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef QED_PATH_H
#define QED_PATH_H
#include <proto/dos.h>
struct QedPath { BPTR parent; unsigned short prefix; char name[256]; };
/* Establish one physical parent; caller zero-initializes and disposes owner. */
int QedPathPrepare(struct QedPath *owner,const char *path,int siblings);
void QedPathRelease(struct QedPath *owner);
int QedPathInfo(const char *name,struct FileInfoBlock *info);
int QedPathSibling(const struct QedPath *owner,const char *leaf,char *result);
int QedPathEqual(const char *a,const char *b);
#endif
