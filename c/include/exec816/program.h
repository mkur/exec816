/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_PROGRAM_H
#define EXEC816_PROGRAM_H
#include <exec/types.h>
#include <exec816/program-start.h>
struct ExecProgramResult { LONG primary,secondary; };
/* NULL spec selects NIL input, shell RAW output and inherited directory.
 * Supplied handles are borrowed for Start; the child owns cloned wrappers.
 * Arguments (0..255 bytes, excluding NUL) are copied. A console is an owned
 * CON handle for independent BREAK/input routing; zero means private BREAK.
 * minimumStack counts reserved bytes, including interrupt headroom.
 * Start acknowledges context/scope setup before returning the owned identity. */
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name,const struct ExecProgramStart *spec);
/* One load reference; release it once. Start retains execution until Collect.
 * Loaded instances are mutable and admit one execution at a time. */
APTR EXEC_CALL ExecLoadProgram(CONST_STRPTR name);
void EXEC_CALL ExecReleaseProgram(APTR image);
ULONG EXEC_CALL ExecStartLoaded(APTR image,const struct ExecProgramStart *spec);
LONG EXEC_CALL ExecCollectProgram(ULONG id,struct ExecProgramResult *result);
LONG EXEC_CALL ExecBreakProgram(ULONG id);
LONG EXEC_CALL ExecWaitProgram(ULONG id,struct ExecProgramResult *result);
/* Borrowed, NUL-terminated Process argument text; NULL outside a Process. */
CONST_STRPTR EXEC_CALL ExecGetArgStr(void);
/* Borrowed completion signal; valid only until the owner collects this child. */
ULONG EXEC_CALL ExecProgramMask(ULONG id);
#endif
