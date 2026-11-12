#include "../../examples/gem-terminal/terminal.h"
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD TerminalLayout[]={sizeof(struct Terminal),offsetof(struct Terminal,paints),
    offsetof(struct Terminal,work),offsetof(struct Terminal,sessions),
    sizeof(struct TerminalSession),offsetof(struct TerminalSession,damageRows),
    offsetof(struct TerminalSession,width),offsetof(struct TerminalSession,column),
    offsetof(struct TerminalSession,mode),offsetof(struct TerminalSession,cells)};
