#include "../../examples/gem-basic/editor.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD BasicLayout[]={
    sizeof(struct BasicApp),sizeof(struct BasicDocument),sizeof(struct BasicEditor),
    offsetof(struct BasicApp,ready),offsetof(struct BasicApp,work),
    offsetof(struct BasicEditor,document),offsetof(struct BasicEditor,caret),
    offsetof(struct BasicEditor,anchor),offsetof(struct BasicEditor,first),
    offsetof(struct BasicEditor,left),offsetof(struct BasicEditor,rows),
    offsetof(struct BasicEditor,columns),offsetof(struct BasicEditor,dirty),
    offsetof(struct BasicEditor,edits),offsetof(struct BasicEditor,paintTurns)
};
