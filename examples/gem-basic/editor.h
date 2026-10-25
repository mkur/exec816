/* SPDX-License-Identifier: MIT */
#ifndef BASIC_EDITOR_H
#define BASIC_EDITOR_H
#include "basic.h"
#include "document.h"
#define BASIC_VIEW_ROWS 30
#define BASIC_VIEW_COLUMNS 80
#define BASIC_REFRESH_BYTES 5120
#define BASIC_MOTION_BYTES 512
/* Private retained appearance. Pixel completeness belongs to AES. */
struct BasicRefresh {
    UBYTE text[BASIC_VIEW_ROWS][BASIC_VIEW_COLUMNS];
    UBYTE attributes[BASIC_VIEW_ROWS][BASIC_VIEW_COLUMNS];
    UBYTE first[BASIC_VIEW_ROWS],end[BASIC_VIEW_ROWS];
    UBYTE forceFirst[BASIC_VIEW_ROWS],forceEnd[BASIC_VIEW_ROWS],valid[BASIC_VIEW_ROWS];
    UBYTE status[BASIC_VIEW_COLUMNS],advance[BASIC_VIEW_ROWS+1];
    ULONG generation,glyphs,statusGlyphs,publications;
    UBYTE *document;
    WORD work[4];
    UWORD top,left,rows,columns;
    UBYTE statusFirst,statusEnd,statusForceFirst,statusForceEnd;
    UBYTE initialized,padding,paddingAdvance,hidden;
    UWORD paddingVisit;
    ULONG documentGeneration;
    UBYTE statusState;
};
typedef char BasicRefreshFits[(sizeof(struct BasicRefresh)<=BASIC_REFRESH_BYTES) ? 1:-1];
/* A settled source identity and one prepared translation. Stored once with the
 * editor; no event pointer or gap-buffer pointer escapes into pending work. */
struct BasicMotion {
    UBYTE *document;
    ULONG generation,epoch,offset[BASIC_VIEW_ROWS];
    UWORD line[BASIC_VIEW_ROWS];
    WORD work[4];
    UWORD top,left,rows,columns;
    WORD sourceRow,targetRow,sourceColumn,targetColumn,copyRows,copyColumns;
    UBYTE settled,linear,prepared,applied;
    ULONG copies,copyPixels,fallbacks;
    ULONG editBefore,editAfter;
    UWORD editFirst,editLast;
    WORD lineDelta;
    UBYTE editReady,wholeLine;
};
typedef char BasicMotionFits[(sizeof(struct BasicMotion)<=BASIC_MOTION_BYTES) ? 1:-1];
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
    union { struct BasicRefresh state;UBYTE bytes[BASIC_REFRESH_BYTES]; } refresh;
    union { struct BasicMotion state;UBYTE bytes[BASIC_MOTION_BYTES]; } motion;
};
/* Borrows an initialized document until AES detach completes. */
WORD BasicEditorPaint(struct BasicEditor *);
WORD BasicEditorRun(struct BasicEditor *);
WORD BasicEditorKey(struct BasicEditor *,WORD,WORD);
void BasicEditorReveal(struct BasicEditor *);
void BasicEditorDamage(struct BasicEditor *,UWORD,UWORD);
void BasicEditorRows(struct BasicEditor *,UWORD,UWORD);
void BasicEditorStatus(struct BasicEditor *,const char *);
void BasicEditorExpose(struct BasicEditor *,WORD,WORD,WORD,WORD);
/* Internal preparation only. The fresh UPDATE view admits actual pixel reuse. */
WORD BasicEditorTranslation(struct BasicEditor *);
ULONG BasicEditorPosition(const struct BasicEditor *,WORD,WORD);
#endif
