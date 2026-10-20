/* Public C/native bridge layout, checked in both compiler modes. */
#include <exec816/program.h>
#include <stddef.h>
__attribute__((section("exec_layout")))
const unsigned short ProgramStartLayout[]={
    sizeof(struct ExecProgramStart),
    offsetof(struct ExecProgramStart,arguments),offsetof(struct ExecProgramStart,input),
    offsetof(struct ExecProgramStart,output),offsetof(struct ExecProgramStart,directory),
    offsetof(struct ExecProgramStart,console),offsetof(struct ExecProgramStart,length),
    offsetof(struct ExecProgramStart,minimumStack),sizeof(struct ExecProgramResult)
};
