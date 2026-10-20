/* SPDX-License-Identifier: MIT */
#ifndef BASIC_DOCUMENT_H
#define BASIC_DOCUMENT_H
#include <exec/types.h>
#define BASIC_BYTES 32768UL
#define BASIC_LINES 4096
#define BASIC_COLUMNS 255
#define BASIC_INDEX_BYTES (4097UL*sizeof(ULONG))
#define BASIC_UNDO_BYTES 16384UL
enum { BASIC_OK=0, BASIC_MEMORY=1, BASIC_CAPACITY=2, BASIC_LINE_CAPACITY=3,
    BASIC_LINE_LENGTH=4, BASIC_CHARACTER=5, BASIC_UNDO_CAPACITY=6,
    BASIC_POSITION=7, BASIC_GENERATION=8 };
struct BasicDocument {
    UBYTE *data,*undo;
    ULONG *line;
    ULONG gap,end,bytes,used,cursor,generation,saved,serial;
    UWORD lines;
};
WORD BasicDocumentInit(struct BasicDocument *);
void BasicDocumentDispose(struct BasicDocument *);
UBYTE BasicByte(const struct BasicDocument *,ULONG);
/* Canonical source accepts only printable ASCII, tab and LF. */
WORD BasicReplace(struct BasicDocument *,ULONG,ULONG,const UBYTE *,ULONG);
WORD BasicUndo(struct BasicDocument *);
WORD BasicRedo(struct BasicDocument *);
WORD BasicDirty(const struct BasicDocument *);
ULONG BasicColumn(const struct BasicDocument *,ULONG);
UWORD BasicLine(const struct BasicDocument *,ULONG);
void BasicCopy(const struct BasicDocument *,ULONG,UBYTE *,ULONG);
#endif
