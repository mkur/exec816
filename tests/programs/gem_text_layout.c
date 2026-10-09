#include "../../examples/gem-text/text.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD TextLayout[]={sizeof(struct TextApp),sizeof(struct TextDocument),sizeof(struct TextLoad),
    offsetof(struct TextApp,ready),offsetof(struct TextApp,first),offsetof(struct TextApp,rows),
    offsetof(struct TextApp,columns),offsetof(struct TextApp,dirty),offsetof(struct TextApp,work),
    offsetof(struct TextApp,document),offsetof(struct TextApp,load),offsetof(struct TextApp,path),
    offsetof(struct TextApp,file),offsetof(struct TextApp,status),offsetof(struct TextApp,paints),
    offsetof(struct TextApp,loads),offsetof(struct TextApp,interruptions),offsetof(struct TextLoad,phase)};
