/* SPDX-License-Identifier: GPL-3.0-only */
#include <gem.h>
#include <exec816/aes.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <string.h>
#include "qed.h"
static unsigned checks;
static WORD globals[15];
/* Inspect target-emitted constants, as in the public layout probes. Calypsi's
 * frontend constant folding does not represent its final pointer layout. */
__attribute__((section("exec_layout")))
const UWORD QedResourceLayout[]={sizeof(void *),sizeof(OBJECT),sizeof(TEDINFO)};
#define CHECK(x) do { ++checks; if(!(x)) return __LINE__; } while(0)

int main(void)
{
    OBJECT *tree,*again,*menu;
    char *text,**slot;
    ULONG baseline;
    WORD i;
    WORD control[5]={112,2,1,0,1},in[2]={R_STRING,0},out[1];
    LONG address[1];
    AESPB pb={control,globals,in,out,NULL,address};
    CHECK(appl_init()>=0);
    baseline=AvailMem(0);
    CHECK(rsrc_load("SYS:QED.RSC"));
    for(i=0;i<NUM_TREE;i++){
        CHECK(rsrc_gaddr(R_TREE,i,(void **)&tree));
        CHECK(tree->ob_next==-1 && tree->ob_head>=0);
    }
    CHECK(rsrc_gaddr(R_TREE,STRINGS,(void **)&tree));
    CHECK(!strcmp((char *)tree[NAMENLOS].ob_spec,"Untitled"));
    CHECK(tree[51].ob_flags&LASTOB);
    for(i=0;i<NUM_FRSTR;i++){
        CHECK(rsrc_gaddr(R_STRING,i,(void **)&text));
        CHECK(rsrc_gaddr(R_FRSTR,i,(void **)&slot));
        CHECK(*slot==text && *text=='[' && strlen(text)<=255);
    }
    aes_call(&pb);
    CHECK(out[0] && rsrc_gaddr(R_STRING,0,(void **)&text) && (ULONG)text==(ULONG)address[0]);
    CHECK(rsrc_gaddr(R_TREE,MENUTREE,(void **)&menu));
    CHECK(menu_bar(menu,1));CHECK(menu_bar(menu,0));
    CHECK(!rsrc_load("SYS:BADFREE.RSC"));
    CHECK(rsrc_gaddr(R_TREE,MENUTREE,(void **)&again) && again==menu);
    CHECK(!rsrc_load("SYS:BADTREE.RSC"));
    CHECK(rsrc_gaddr(R_TREE,MENUTREE,(void **)&again) && again==menu);
    CHECK(rsrc_gaddr(R_TREE,REPLACE,(void **)&tree));
    {
        TEDINFO *ted=(TEDINFO *)tree[RPTEXT1].ob_spec;
        char *field=(char *)ted->te_ptext;
        CHECK(ted->te_txtlen>50 && ted->te_txtlen<=128);
        field[0]='Q';field[1]=0;CHECK(!strcmp((char *)ted->te_ptext,"Q"));
    }
    CHECK(!rsrc_gaddr(R_STRING,NUM_FRSTR,(void **)&text) && !text);
    CHECK(!rsrc_gaddr(R_FRSTR,-1,(void **)&slot) && !slot);
    CHECK(!rsrc_gaddr(R_TREE,NUM_TREE,(void **)&tree) && !tree);
    CHECK(rsrc_free());CHECK(AvailMem(0)==baseline);
    CHECK(rsrc_load("SYS:QED.RSC"));CHECK(rsrc_free());
    CHECK(AvailMem(0)==baseline);
    CHECK(appl_exit());SetIoErr(0);
    return -321;
}
