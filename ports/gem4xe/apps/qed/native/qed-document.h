/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef QED_DOCUMENT_H
#define QED_DOCUMENT_H
#include "global.h"
#include <proto/dos.h>
/* One detached candidate. Poll returns pending / ready / failed. */
bool QedDocumentBegin(const char *path);
bool QedDocumentReread(void);
short QedDocumentPoll(void);
void QedDocumentCancel(void);
LONG QedDocumentError(void);
const char *QedDocumentName(void);
RINGP QedDocumentRing(void);
void QedDocumentCommit(TEXTP text);
#endif
