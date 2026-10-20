/* SPDX-License-Identifier: MIT */
#ifndef BASIC_ASSIST_H
#define BASIC_ASSIST_H
#include "document.h"
#define BASIC_FIND_BYTES 80
#define BASIC_PROCEDURES 256
enum { BASIC_LEX_TEXT=1,BASIC_LEX_STRING=2,BASIC_LEX_COMMENT=3,BASIC_LEX_KEYWORD=4 };
struct BasicFind {
    ULONG generation,start,at,matched,limit,result;
    UWORD length,index,fold,done;
    UBYTE needle[BASIC_FIND_BYTES];
    UWORD prefix[BASIC_FIND_BYTES];
};
struct BasicReplaceJob {
    struct BasicFind find;
    UBYTE replacement[BASIC_FIND_BYTES],*buffer;
    ULONG first,last,count,at,out,span,bytes,copyEnd;
    UWORD size,phase,error;
};
WORD BasicReplaceBegin(struct BasicReplaceJob *,const struct BasicDocument *,const UBYTE *,UWORD,const UBYTE *,UWORD,WORD);
/* 0 pending, 1 complete, -1 rejected/stale; job.error is the document result. */
WORD BasicReplaceStep(struct BasicReplaceJob *,struct BasicDocument *);
void BasicReplaceCancel(struct BasicReplaceJob *);
struct BasicProcedure { UWORD first,last;char name[32]; };
struct BasicAssist {
    ULONG generation;
    UWORD scan,count,open,overflow;
    struct BasicProcedure procedures[BASIC_PROCEDURES];
    UBYTE hidden[512];
};
WORD BasicFindBegin(struct BasicFind *,const struct BasicDocument *,const UBYTE *,UWORD,ULONG,WORD);
/* At most 1024 byte comparisons per step; 0 pending, 1 found, -1 end/stale. */
WORD BasicFindStep(struct BasicFind *,const struct BasicDocument *);
WORD BasicReplaceMatches(struct BasicDocument *,const UBYTE *,UWORD,const UBYTE *,UWORD,WORD,ULONG *);
WORD BasicIndent(struct BasicDocument *,ULONG,ULONG,ULONG *);
void BasicLexLine(const struct BasicDocument *,UWORD,UBYTE *);
void BasicAssistBegin(struct BasicAssist *,const struct BasicDocument *);
WORD BasicAssistStep(struct BasicAssist *,const struct BasicDocument *);
WORD BasicProcedureNamed(const struct BasicAssist *,const char *);
WORD BasicFold(struct BasicAssist *,UWORD);
WORD BasicHidden(const struct BasicAssist *,UWORD);
void BasicUnfold(struct BasicAssist *,UWORD);
UWORD BasicVisible(const struct BasicAssist *,UWORD,UWORD);
#endif
