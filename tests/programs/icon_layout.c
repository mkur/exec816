#include <gem.h>
#include <stddef.h>
__attribute__((section("exec_layout")))
const UWORD IconLayout[]={sizeof(ICONBLK),offsetof(ICONBLK,ib_pmask),
    offsetof(ICONBLK,ib_pdata),offsetof(ICONBLK,ib_ptext),offsetof(ICONBLK,ib_char),
    offsetof(ICONBLK,ib_wicon),offsetof(ICONBLK,ib_hicon),offsetof(ICONBLK,ib_htext),
    sizeof(CICON),offsetof(CICON,num_planes),offsetof(CICON,col_data),offsetof(CICON,col_mask),
    offsetof(CICON,sel_data),offsetof(CICON,sel_mask),offsetof(CICON,next_res),
    sizeof(CICONBLK),offsetof(CICONBLK,monoblk),offsetof(CICONBLK,mainlist)};
