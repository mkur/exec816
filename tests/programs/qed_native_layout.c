/* Focused executable coverage for the general five-bank C image profile. */
#include "qed-native.h"
#include <string.h>
#include <cflib.h>
#include <exec816/runtime.h>
#include <exec816/program.h>
#include <proto/dos.h>
extern void QedLayoutFirst(void);
extern void QedLayoutLast(void);
extern const UWORD QedLayoutTable;
static volatile ULONG layoutWrites;
static volatile UWORD layoutSeed=0x1234;
int main(void)
{
#ifdef QED_TEST_LIMITS
    ULONG available;
#endif
    char number[34],text[8]="AbZ";
    GRECT a={2,3,6,7},b={4,1,8,8};
    QedLayoutFirst();QedLayoutLast();
    ExecYield();
    if(QedLayoutTable!=0xabcd || layoutWrites || layoutSeed!=0x1234)return 107;
    layoutWrites++;layoutSeed++;
    if(!rc_intersect(&a,&b) || b.g_x!=4 || b.g_y!=3 || b.g_w!=4 || b.g_h!=6)return 101;
    rc_union(&a,&b);
    if(b.g_x!=2 || b.g_y!=3 || b.g_w!=6 || b.g_h!=7)return 102;
    if(stricmp("aBc","ABC") || strnicmp("AbX","aBy",2))return 103;
    if(strcmp(strlwr(text),"abz") || strcmp(strupr(text),"ABZ"))return 104;
    if(strcmp(ltoa(-2147483647L-1,number,10),"-2147483648"))return 105;
    if(strcmp(ultoa(4294967295UL,number,16),"ffffffff"))return 106;
    if(gem_to_norm(K_CTRL,0x1e01)!=(NKF_CTRL|'A'))return 108;
    if(gem_to_norm(0,0x4800)!=(NKF_FUNC|NK_UP))return 109;
#ifdef QED_TEST_LIMITS
    if(ExecStartProgram("SYS:COUNT.APP",NULL) || IoErr()!=QED_BAD_FORMAT)return 110;
    available=AvailMem(0);
    if(ExecStartProgram("SYS:SPAN.APP",NULL) || IoErr()!=QED_BAD_FORMAT)return 111;
    if(AvailMem(0)!=available)return 112;
    if(ExecStartProgram("SYS:COUNT.APP",NULL) || IoErr()!=QED_BAD_FORMAT)return 113;
    if(AvailMem(0)!=available)return 114;
    SetIoErr(0);
#endif
    return -321;
}
