/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_CONSOLE_H
#define EXEC816_CONSOLE_H
#include <exec/types.h>

/* Created units belong to the calling Task. Zero reports admission failure.
 * Format a nonzero unit as CON:xxxxxxxx or RAW:xxxxxxxx (eight hex digits).
 * Destroy refuses live windows, streams, reads, writes and cancellation scopes.
 * Close the window and its streams before destroying the unit. */
ULONG EXEC_CALL ExecConsoleCreate(UWORD width,UWORD height);
LONG EXEC_CALL ExecConsoleDestroy(ULONG unit);
/* Change an owned CON endpoint's mode with no active readers.
 * Use EXEC_CONSOLE_ATASCII before starting a FastBasic child. */
#define EXEC_CONSOLE_ATASCII 0x40
LONG EXEC_CALL ExecConsoleMode(BPTR console,UWORD mode);
/* Snapshot applied mode flags without clearing input or claiming a reader.
 * Returns 0..0xe0 or -1 with IoErr on failure. */
LONG EXEC_CALL ExecConsoleGetMode(BPTR console);
/* Bind an owned 64x20 console to a closed, fixed-size GEM window. Its work
 * area must be 512x160, aligned to 8 pixels. The console worker paints it;
 * the owning application handles WM_TOPPED/MOVED/CLOSED in the usual way.
 * Binding lasts through wind_close and retires with wind_delete. */
WORD EXEC_CALL ExecAESConsole(WORD window,ULONG unit);
#endif
