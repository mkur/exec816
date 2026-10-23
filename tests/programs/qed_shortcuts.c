/* Actual CF-Lib shortcut parser, with fixed labels and notification sinks.
 * No input delivery, native menu painting or loaded-editor claim here.
 */
#include "qed-runtime.h"
#include "cflib.h"
#include <string.h>

static OBJECT tree[11];
OBJECT *__menu_tree=tree;
short __menu_disabled;
static WORD normalized;
void get_string(OBJECT *objects,WORD item,char *text)
{
    strcpy(text,(const char *)(ULONG)objects[item].ob_spec);
}
WORD QedRecordMenuNormal(OBJECT *objects,WORD title,WORD normal)
{
    if(objects!=tree || title!=8 || normal) return 0;
    ++normalized;return 1;
}
static int body(int argc,char **argv)
{
    char label[]=" Select ^A";
    WORD title,item,i;
    tree[0].ob_head=1;tree[0].ob_tail=4;
    tree[1].ob_head=2;tree[2].ob_head=3;
    tree[3].ob_next=8;tree[8].ob_next=2;
    tree[4].ob_head=5;tree[5].ob_head=6;tree[5].ob_next=7;
    tree[6].ob_type=G_STRING;tree[6].ob_spec=(ULONG)" About ";
    tree[7].ob_head=9;tree[7].ob_next=4;
    tree[9].ob_type=G_STRING;tree[9].ob_spec=(ULONG)label;tree[9].ob_next=7;
    for(i=1;i<=26;++i){
        label[9]='A'+i-1;
        if(!is_menu_key((0x1e<<8)|i,K_CTRL,&title,&item) || title!=8 || item!=9)
            return 100+i;
        if(!is_menu_key((0x1e<<8)|('a'+i-1),K_CTRL,&title,&item))return 200+i;
        if(is_menu_key((0x1e<<8)|i,0,&title,&item))return 300+i;
    }
    tree[9].ob_state=OS_DISABLED;
    if(is_menu_key(0x1e1a,K_CTRL,&title,&item) || normalized!=52)return 401;
    return -321;
}
int main(void){return QedRuntimeRun(body);}
