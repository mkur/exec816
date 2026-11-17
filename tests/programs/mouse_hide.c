/* Production draw_Mouse; hardware is substituted to exercise target lifetime. */
#include "aes-private.h"
#include "gem-drawing.h"
#include <proto/exec.h>
#include <string.h>

UWORD checks,failures,firstFailure;
static UBYTE page[4096];
static UWORD fault,cursorMasksReady,cursorVisible,copies,compares,hides,renders;
static UWORD renderedX,renderedY,renderedVisible,late,publishFault;
static struct { UWORD operationPending; } display;
static struct AESMouseForm cursorForm;
static struct AESMouseState mouse;

static void Check(int okay)
{ ++checks;if (!okay) { if (!failures) firstFailure=checks;++failures; } }
static void flush(void) { }
static void cursor_hide(void) { ++hides; }
static void cursor_render(UWORD x,UWORD y,UWORD visible)
{
    ++renders;renderedX=x;renderedY=y;renderedVisible=visible;
    if (late) {
        mouse.visible=1;mouse.form.kind=AES_USER_DEF;mouse.form.words[3]=7;
        ++mouse.revision;late=0;
    }
    if (publishFault) fault=DISPLAY_DEVICE_FAULT;
}
static void *Copy(void *to,const void *from,size_t size)
{ ++copies;return memcpy(to,from,size); }
static int Compare(const void *a,const void *b,size_t size)
{ ++compares;return memcmp(a,b,size); }

#define memcpy Copy
#define memcmp Compare
#include "mouse-hide-body.inc"
#undef memcpy
#undef memcmp

static void Reset(void)
{
    copies=compares=hides=renders=fault=late=publishFault=0;
    display.operationPending=0;
}

LONG EXEC_CALL HideRun(ULONG value)
{
    (void)value;
    Reset();
    cursorForm.kind=AES_ARROW;cursorMasksReady=1;cursorVisible=1;
    mouse.x=121;mouse.y=89;mouse.visible=0;mouse.revision=1;
    mouse.form.kind=AES_USER_DEF;mouse.form.words[2]=1;mouse.form.words[3]=9;
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(!copies && !compares && !hides && renders==1);
    Check(renderedX==121 && renderedY==89 && !renderedVisible);
    Check(cursorForm.kind==AES_ARROW && cursorMasksReady==1);
    Check(mouse.completed==1 && !mouse.status);

    /* Explicit form applies while already hidden retain their old path. */
    Reset();++mouse.revision;mouse.form.words[3]=4;
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(copies==2 && !compares && hides==1 && mouse.completed==2);
    Reset();mouse.visible=1;++mouse.revision;
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(copies==1 && compares==1 && !hides && renders==1);
    Check(cursorForm.kind==AES_USER_DEF && cursorForm.words[3]==4);
    Check(!cursorMasksReady && renderedVisible && mouse.completed==3);
    Reset();cursorMasksReady=1;++mouse.revision;
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(copies==1 && compares==1 && !hides && cursorMasksReady==1);

    /* Completion acknowledges the captured revision, preserving a late show. */
    Reset();mouse.visible=0;++mouse.revision;late=1;
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(!copies && !compares && !hides && !renderedVisible);
    Check(mouse.completed==5 && mouse.revision==6 && mouse.visible);
    Check(cursorForm.words[3]==4 && mouse.form.words[3]==7);
    Reset();
    Check(draw_Mouse(&mouse)==DISPLAY_OK);
    Check(copies==2 && compares==1 && hides==1 && renderedVisible);
    Check(cursorForm.words[3]==7 && mouse.completed==6);

    Reset();mouse.visible=0;++mouse.revision;publishFault=1;
    Check(draw_Mouse(&mouse)==DISPLAY_DEVICE_FAULT);
    Check(!copies && !compares && !hides && !renderedVisible);
    Check(mouse.status==DISPLAY_DEVICE_FAULT && mouse.completed==6);
    Reset();mouse.status=0;display.operationPending=1;
    Check(draw_Mouse(&mouse)==DISPLAY_BUSY);
    Check(!copies && !compares && !renders && mouse.completed==6);
    return failures;
}

int main(void) { return 0; }
