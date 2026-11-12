/* SPDX-License-Identifier: MIT */
#ifndef GEM_TERMINAL_H
#define GEM_TERMINAL_H
#include <gem.h>
#include <proto/exec.h>
#include <exec816/console-view.h>
#include <exec816/aes-wait.h>
#include <exec816/shell-sessions.h>
#define TERM_WIDTH 64
#define TERM_HEIGHT 20
#define TERM_CELLS (TERM_WIDTH*TERM_HEIGHT)
#define TERM_CONTROLS 16
struct TerminalSession {
    ULONG identity,unit,view,revision,route,damageRows;
    UWORD width,height,column,row,mode,coherent;
    UBYTE cells[TERM_CELLS];
};
struct Terminal {
    WORD id,window,vdi,opened,selected,dirty,focused;
    ULONG paints;
    WORD work[4],input[11],output[57],message[8],glyphs[TERM_WIDTH];
    struct TerminalSession sessions[EXEC_CONSOLE_VIEW_SLOTS];
    struct ShellSessionQuery directory;
    struct ExecConsoleViewDirectory sources;
    ULONG selection,activation;
    struct ShellSessionMessage request;
    struct MsgPort *replies;
    ULONG wake;
    struct ExecAESWaitSpec wait;
    struct ExecConsoleViewInput inputPacket;
};
WORD TerminalPlatformOpen(struct Terminal *);
void TerminalPlatformClose(struct Terminal *);
WORD TerminalPlatformRefresh(struct Terminal *);
WORD TerminalPlatformAction(struct Terminal *,UBYTE,ULONG);
WORD TerminalPlatformWait(struct Terminal *);
WORD TerminalPlatformSelect(struct Terminal *,WORD);
WORD TerminalPaint(struct Terminal *,const WORD *);
#endif
