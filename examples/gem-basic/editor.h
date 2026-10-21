/* SPDX-License-Identifier: MIT */
#ifndef BASIC_EDITOR_H
#define BASIC_EDITOR_H
#include "basic.h"
#include "document.h"
struct BasicEditor {
    struct BasicApp app;
    struct BasicDocument document;
    ULONG caret,anchor;
    UWORD first,left,rows,columns;
    WORD damageFirst,damageEnd,dirty,publish,dragging,mx,my;
    WORD minw,minh,sliderSize,sliderPosition;
    OBJECT menu[48];
    char row[81],status[81];
    ULONG edits,paintTurns;
    UBYTE colors[80];
};
/* Borrows an initialized document until AES detach completes. */
WORD BasicEditorPaint(struct BasicEditor *);
WORD BasicEditorRun(struct BasicEditor *);
WORD BasicEditorKey(struct BasicEditor *,WORD,WORD);
void BasicEditorReveal(struct BasicEditor *);
void BasicEditorDamage(struct BasicEditor *,UWORD,UWORD);
ULONG BasicEditorPosition(const struct BasicEditor *,WORD,WORD);
#endif
