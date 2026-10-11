/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_PROGRAM_H
#define EXEC816_PROGRAM_H
#include <exec/types.h>
struct ExecProgramResult { LONG primary,secondary; };
/* Native/C disk programs, copied arguments, NIL input and shell RAW output.
 * Length excludes NUL (0..255); NULL/zero supplies an empty tail.
 * One parent owns the returned Process identity until collection succeeds. */
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name,CONST_STRPTR arguments,UWORD length);
LONG EXEC_CALL ExecCollectProgram(ULONG id,struct ExecProgramResult *result);
LONG EXEC_CALL ExecBreakProgram(ULONG id);
LONG EXEC_CALL ExecWaitProgram(ULONG id,struct ExecProgramResult *result);
/* Borrowed, NUL-terminated Process argument text; NULL outside a Process. */
CONST_STRPTR EXEC_CALL ExecGetArgStr(void);
/* Borrowed completion signal; valid only until the owner collects this child. */
ULONG EXEC_CALL ExecProgramMask(ULONG id);
#endif
