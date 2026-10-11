#include "../../examples/gem-dialog/dialog.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD DialogLayout[]={sizeof(struct DialogApp),
    offsetof(struct DialogApp,ready),offsetof(struct DialogApp,phase),
    offsetof(struct DialogApp,accepted),offsetof(struct DialogApp,paints),
    offsetof(struct DialogApp,interruptions),offsetof(struct DialogApp,work),
    offsetof(struct DialogApp,home),offsetof(struct DialogApp,text),
    offsetof(struct DialogApp,path),offsetof(struct DialogApp,file),
    offsetof(struct DialogApp,directory),offsetof(struct DialogApp,selection),
    offsetof(struct DialogApp,fileButton),offsetof(struct DialogApp,fileResult)};
