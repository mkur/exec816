#include <exec816/fastbasic-interpreter.h>
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD BasicInterpreterLayout[]={
    sizeof(struct ExecBasicSource),sizeof(struct ExecBasicResult),
    offsetof(struct ExecBasicSource,source),offsetof(struct ExecBasicSource,result),
    offsetof(struct ExecBasicResult,job),offsetof(struct ExecBasicResult,phase),
    offsetof(struct ExecBasicResult,cause),offsetof(struct ExecBasicResult,message)
};
