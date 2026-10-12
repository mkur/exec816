#include <gem.h>
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD IconLayout[]={sizeof(ICONBLK),offsetof(ICONBLK,ib_pmask),
    offsetof(ICONBLK,ib_pdata),offsetof(ICONBLK,ib_ptext),offsetof(ICONBLK,ib_char),
    offsetof(ICONBLK,ib_wicon),offsetof(ICONBLK,ib_hicon),offsetof(ICONBLK,ib_htext)};
