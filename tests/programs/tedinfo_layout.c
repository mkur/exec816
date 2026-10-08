#include <gem.h>
#include <proto/exec.h>
#include <stddef.h>
#include "application-hosted.h"
WORD gl_wchar=8,gl_hchar=8,intin[64];
__attribute__((section("exec_layout")))
const UWORD TedLayout[]={sizeof(OBJECT),sizeof(TEDINFO),
    offsetof(TEDINFO,te_ptext),offsetof(TEDINFO,te_ptmplt),offsetof(TEDINFO,te_pvalid),
    offsetof(TEDINFO,te_font),offsetof(TEDINFO,te_fontid),offsetof(TEDINFO,te_just),
    offsetof(TEDINFO,te_color),offsetof(TEDINFO,te_fontsize),offsetof(TEDINFO,te_thickness),
    offsetof(TEDINFO,te_txtlen),offsetof(TEDINFO,te_tmplen)};
volatile WORD TedObserved[7];
static TEDINFO ted;
static OBJECT object;
LONG EXEC_CALL TedProbe(ULONG unused)
{
    char *storage=AllocMem(131088UL,MEMF_PUBLIC|MEMF_LINEAR),*text;
    TEDINFO *p;
    LONG result=0;
    WORD i,n;
    GRECT r={56,52,128,8};
    (void)unused;
    if (!storage) return 1;
    text=(char *)((((ULONG)storage+65535UL)&0xffff0000UL)+65532UL);
    ted.te_ptext=(ULONG)text;ted.te_ptmplt=(ULONG)"____";ted.te_pvalid=(ULONG)"9";
    ted.te_font=IBM;ted.te_just=TE_RIGHT;ted.te_thickness=-1;ted.te_txtlen=12;
    object.ob_spec=(ULONG)&ted;object.ob_type=G_BOXTEXT;
    p=(TEDINFO *)(ULONG)object.ob_spec;
    ((char *)(ULONG)p->te_ptext)[0]='-';((char *)(ULONG)p->te_ptext)[10]='7';
    ((char *)(ULONG)p->te_ptext)[11]=0;
    if ((ULONG)p<=65535UL || p->te_ptext<=65535UL || text[0]!='-' || text[10]!='7' ||
        text[11] || p->te_thickness!=-1 || ((char *)(ULONG)p->te_pvalid)[0]!='9') result=2;
    for (i=1;i<10;++i) text[i]='0';
    n=gr_just(TE_RIGHT,IBM,text,128,8,&r);
    TedObserved[0]=n;TedObserved[1]=r.g_x;TedObserved[2]=r.g_y;TedObserved[3]=r.g_w;TedObserved[4]=r.g_h;TedObserved[5]=gl_wchar;TedObserved[6]=gl_hchar;
    if (n!=11) result=1000+n;
    else if (r.g_x!=96 || r.g_y!=52 || r.g_w!=88 || r.g_h!=8) result=2000+r.g_w;
    FreeMem(storage,131088UL);
    return result;
}
int main(void) { return 0; }
