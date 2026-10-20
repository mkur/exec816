/* Generated from abi/process.json; do not edit. */
#ifndef EXEC816_PROGRAM_START_H
#define EXEC816_PROGRAM_START_H
#include <exec/types.h>
struct ExecProgramStart {
    CONST_STRPTR arguments;
    BPTR input;
    BPTR output;
    BPTR directory;
    BPTR console;
    UWORD length;
    UWORD minimumStack;
};
#endif
