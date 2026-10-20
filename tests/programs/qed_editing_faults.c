/* Development-only refusal at the actual editor line-allocation boundary.
 * Successful operations always use the real donor allocator and public GUI.
 */
#include "global.h"
#include "memory.h"
#include "window.h"
#include "menu.h"
#include "ausgabe.h"
#include <proto/dos.h>
#include <exec816/aes.h>
#include <proto/exec.h>
#include <stddef.h>

volatile unsigned short QedEditFailLine,QedEditFailureHits;
volatile unsigned short QedEditKeyCalls,QedLastKey,QedLastQualifiers;
volatile unsigned short QedGlobalKeyCalls;
volatile unsigned short QedCursorPaints,QedPaintedBlink,QedPaintedX;
volatile long QedPaintedY;
volatile unsigned short QedSelectionFailClock,QedSelectionClockFailures;
void QedEditCursor(WINDOWP window,TEXTP text);

struct IORequest * EXEC_CALL QedSelectionCreateIORequest(struct MsgPort *port,ULONG bytes)
{
    if(QedSelectionFailClock){
        QedSelectionFailClock=0;++QedSelectionClockFailures;
        SetIoErr(ERROR_NO_FREE_STORE);return NULL;
    }
    return CreateIORequest(port,bytes);
}

void cursor(WINDOWP window,TEXTP text)
{
    QedEditCursor(window,text);
    QedPaintedBlink=text->blink;QedPaintedX=text->xpos;QedPaintedY=text->ypos;
    ++QedCursorPaints;
}

bool QedEditKeyWindow(WINDOWP window,short qualifiers,short key)
{
    bool result=key_window(window,qualifiers,key);
    QedLastKey=key;QedLastQualifiers=qualifiers;++QedEditKeyCalls;
    return result;
}
bool QedEditGlobalKey(short qualifiers,short key)
{
    bool result=key_global(qualifiers,key);
    ++QedGlobalKeyCalls;return result;
}
LINEP QedEditNewCol(char *text,short length)
{
    if(QedEditFailLine && --QedEditFailLine==0){
        ++QedEditFailureHits;
        SetIoErr(ERROR_NO_FREE_STORE);return NULL;
    }
    return new_col(text,length);
}

/* Observers read target-emitted offsets, never host compiler sizeof guesses. */
const unsigned short QedEditingLayout[]={
    sizeof(TEXT),offsetof(TEXT,text),offsetof(TEXT,cursor_line),
    offsetof(TEXT,xpos),offsetof(TEXT,ypos),offsetof(TEXT,moved),
    offsetof(TEXT,filename),offsetof(TEXT,block),offsetof(TEXT,z1),
    offsetof(TEXT,x1),offsetof(TEXT,z2),offsetof(TEXT,x2),
    sizeof(LINE),offsetof(LINE,next),offsetof(LINE,len),
    offsetof(RING,head),offsetof(RING,tail),offsetof(RING,lines),offsetof(RING,ending),
    offsetof(TEXT,link),sizeof(WINDOW),offsetof(WINDOW,doc),offsetof(WINDOW,work),
    offsetof(TEXT,blink),offsetof(TEXT,cursor),offsetof(WINDOW,title),offsetof(WINDOW,info),
    offsetof(struct ExecAESContext,endpoint),
    offsetof(struct ExecAESContext,timer)+offsetof(struct ExecAESTimer,state),
    offsetof(TEXT,block_dir),offsetof(struct Task,tc_State)
};
