#include "../../examples/gem-panel/panel.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD PanelLayout[]={sizeof(struct Panel),offsetof(struct Panel,ready),
    offsetof(struct Panel,actions),offsetof(struct Panel,paints),offsetof(struct Panel,work),
    offsetof(struct Panel,tree),offsetof(struct Panel,status),offsetof(struct Panel,focus),offsetof(struct Panel,armed)};
