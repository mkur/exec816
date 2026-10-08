#include "../../examples/gem-counter/counter.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD CounterLayout[]={sizeof(struct Counter),offsetof(struct Counter,ready),
    offsetof(struct Counter,count),offsetof(struct Counter,paints),offsetof(struct Counter,message),
    offsetof(struct Counter,work),offsetof(struct Counter,label)};
