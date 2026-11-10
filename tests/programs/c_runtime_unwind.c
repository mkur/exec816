/* SPDX-License-Identifier: MIT. Only C activations lie between the target and
 * longjmp. Native calls and real IRQ/NMI return before the jump is attempted. */
#include <setjmp.h>
#include <exec816/runtime.h>
#include <proto/exec.h>
static jmp_buf target;
extern void ClobberAndJump(jmp_buf);
extern int CheckJumpRegisters(jmp_buf);
__attribute__((section("exec_layout"))) const UWORD JumpLayout[]={sizeof(jmp_buf)};
static int preserved(UWORD *pointer)
{
    if (!setjmp(target)) ClobberAndJump(target);
    return pointer && *pointer==0x5a3c;
}
static unsigned int visited,executions;
static volatile unsigned long computing;
static void nested(unsigned int depth)
{
    volatile unsigned int canary[8];
    unsigned int i;
    for (i=0;i<8;++i) canary[i]=depth+i;
    for (i=0;i<256;++i) computing=computing*1664525UL+1013904223UL;
    ExecYield();
    if (depth) nested(depth-1);
    else { visited=1;longjmp(target,-321); }
    visited=99;
}
int main(void)
{
    volatile unsigned int canary=0x5a3c;
    visited=0;
    switch (setjmp(target)) {
    case 0:nested(4);return 1;
    case -321:break;
    default:return 2;
    }
    if (visited!=1 || canary!=0x5a3c) return 3;
    switch (setjmp(target)) {
    case 0:
        if (visited==1) { visited=2;longjmp(target,0); }
        return 4;
    case 1:break;
    default:return 5;
    }
    if (visited!=2 || canary!=0x5a3c) return 6;
    if (!preserved((UWORD *)&canary)) return 7;
    if (!CheckJumpRegisters(target)) return 8;
    if (computing!=(executions ? 1300132352UL:2854566144UL)) return 9;
    return -321-executions++;
}
