/* SPDX-License-Identifier: MIT */
#ifndef GEM_TEXT_DOCUMENT_H
#define GEM_TEXT_DOCUMENT_H
#include <proto/dos.h>
#define TEXT_BYTES 65536UL
#define TEXT_LINES 4096
#define TEXT_INDEX_BYTES ((TEXT_LINES+1UL)*sizeof(ULONG))
#define TEXT_LINE_LIMIT 1001L
struct TextDocument {
    UBYTE *data;
    ULONG *line,bytes;
    UWORD lines;
    char path[128];
};
struct TextLoad {
    struct TextDocument candidate;
    struct FileInfoBlock info;
    BPTR file;
    LONG error;
    WORD phase,start,cr;
    UBYTE probe;
};
void TextDispose(struct TextDocument *);
void TextBegin(struct TextLoad *,const char *);
void TextCancel(struct TextLoad *);
/* 0: work remains, 1: committed, -1: failed. One bounded loading unit. */
WORD TextStep(struct TextLoad *,struct TextDocument *);
void TextRow(const struct TextDocument *,UWORD,char *,WORD);
WORD TextArgument(const char *,char *);
#endif
