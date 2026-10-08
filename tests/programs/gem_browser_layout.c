#include "../../examples/gem-browser/browser.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD BrowserLayout[]={sizeof(struct Browser),offsetof(struct Browser,ready),offsetof(struct Browser,work),
    offsetof(struct Browser,tree),offsetof(struct Browser,path),offsetof(struct Browser,names),offsetof(struct Browser,status),
    offsetof(struct Browser,count),offsetof(struct Browser,selected),offsetof(struct Browser,launches),offsetof(struct Browser,child),offsetof(struct Browser,bar),
    offsetof(struct Browser,menuInstalled),offsetof(struct Browser,menuEnabled)};
