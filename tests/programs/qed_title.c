/* Actual bounded title formatter; a forwarding sink records its borrowed text. */
#include "qed-runtime.h"
#include "global.h"
#include "window.h"
#include <exec816/desktop-geometry.h>
#include <string.h>
static WINDOW view;
static short calls,bad;
WORD QedTitle(WORD handle,WORD field,const char *text)
{
    ++calls;
    if(handle!=1 || field!=WF_NAME || text!=view.title || strlen(text)>=DESKTOP_TITLE_BYTES)bad=1;
    return 1;
}
static int body(int argc,char **argv)
{
    static char path[256];unsigned short i;
    memset(&view,0xa7,sizeof(view));view.flags=WI_OPEN;view.handle=1;view.kind=NAME;
    memset(path,'a',255);path[255]=0;set_wtitle(&view,path);
    if(bad || calls!=1 || strlen(view.title)!=64 || view.title[0]!=' ' || view.title[63]!=' ')return 100;
    for(i=65;i<sizeof(view.title);i++)if((unsigned char)view.title[i]!=0xa7)return 101;
    for(i=0;i<sizeof(view.info);i++)if((unsigned char)view.info[i]!=0xa7)return 102;
    view.flags|=WI_CHANGED;set_wtitle(&view,path);
    if(bad || calls!=2 || strlen(view.title)!=64 || memcmp(view.title," *",2))return 103;
    view.flags&=~WI_CHANGED;set_wtitle(&view,"SYS:A.TXT");
    if(bad || calls!=3 || strcmp(view.title," SYS:A.TXT "))return 104;
    return -321;
}
int main(void){return QedRuntimeRun(body);}
