#include "../../examples/gem-basic/build-job.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD BasicBuildLayout[]={
    sizeof(struct BasicBuildJob),offsetof(struct BasicBuildJob,phase),
    offsetof(struct BasicBuildJob,job),offsetof(struct BasicBuildJob,child),
    offsetof(struct BasicBuildJob,unit),offsetof(struct BasicBuildJob,caret),
    offsetof(struct BasicBuildJob,cause),offsetof(struct BasicBuildJob,compilerResult),
    offsetof(struct BasicBuildJob,programResult),offsetof(struct BasicBuildJob,diagnostic),
    offsetof(struct BasicBuildJob,window),offsetof(struct BasicBuildJob,source),
    offsetof(struct BasicBuildJob,target)
};
