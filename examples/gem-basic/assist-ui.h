/* SPDX-License-Identifier: MIT */
#ifndef BASIC_ASSIST_UI_H
#define BASIC_ASSIST_UI_H
#include "editor.h"
enum { BASIC_ASSIST_FIND=1,BASIC_ASSIST_NEXT,BASIC_ASSIST_REPLACE,BASIC_ASSIST_PROC_NEXT,BASIC_ASSIST_PROC_PREVIOUS,BASIC_ASSIST_FOLD };
void BasicAssistanceInit(struct BasicEditor *);
void BasicAssistanceDispose(void);
void BasicAssistanceRequest(WORD);
void BasicAssistanceCancel(struct BasicEditor *);
WORD BasicAssistanceWork(const struct BasicEditor *);
WORD BasicAssistanceBusy(void);
WORD BasicAssistanceIndent(struct BasicEditor *,ULONG,ULONG,ULONG *);
WORD BasicAssistanceStep(struct BasicEditor *);
UWORD BasicAssistanceLine(const struct BasicEditor *,UWORD);
UWORD BasicAssistanceRow(const struct BasicEditor *,UWORD);
UWORD BasicAssistancePrevious(const struct BasicEditor *,UWORD);
UWORD BasicAssistanceNext(const struct BasicEditor *,UWORD);
UWORD BasicAssistanceTop(const struct BasicEditor *);
UWORD BasicAssistanceCount(const struct BasicEditor *);
void BasicAssistanceReveal(struct BasicEditor *,UWORD);
void BasicAssistanceSelect(struct BasicEditor *,ULONG,ULONG);
/* Returns a common source colour only for a whole line without tabs. */
UBYTE BasicAssistanceCompose(struct BasicEditor *,UWORD);
#endif
