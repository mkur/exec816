/* Development observer layout; no public ABI. */
#include "../../examples/gem-widget/widget.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD WidgetLayout[]={
    sizeof(struct Widget),
    offsetof(struct Widget,id),offsetof(struct Widget,window),
    offsetof(struct Widget,opened),offsetof(struct Widget,ready),
    offsetof(struct Widget,actions),offsetof(struct Widget,paints),
    offsetof(struct Widget,message),offsetof(struct Widget,work),
    offsetof(struct Widget,tree),offsetof(struct Widget,label)
};
