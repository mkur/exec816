/* SPDX-License-Identifier: MIT */
#ifndef EXEC816_PROGRAM_H
#define EXEC816_PROGRAM_H
#include <exec/types.h>
struct ExecProgramResult { LONG primary,secondary; };
/* Native Exec disk commands, empty arguments, NIL input and shell RAW output.
 * One parent owns the returned Process identity until collection succeeds. */
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name);
LONG EXEC_CALL ExecCollectProgram(ULONG id,struct ExecProgramResult *result);
LONG EXEC_CALL ExecBreakProgram(ULONG id);
LONG EXEC_CALL ExecWaitProgram(ULONG id,struct ExecProgramResult *result);
#endif
