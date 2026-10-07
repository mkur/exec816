#include "../../examples/gem-input/input.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD InputLayout[]={sizeof(struct InputApp),offsetof(struct InputApp,ready),
    offsetof(struct InputApp,activations),offsetof(struct InputApp,paints),offsetof(struct InputApp,message),
    offsetof(struct InputApp,work),offsetof(struct InputApp,key),offsetof(struct InputApp,clicks),offsetof(struct InputApp,down),
    offsetof(struct InputApp,armed),offsetof(struct InputApp,tick)};
