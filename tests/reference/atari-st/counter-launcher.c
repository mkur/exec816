/* SPDX-License-Identifier: MIT
 * Resource-free MagiC desktop launcher for two ordinary GEM processes. */
#include <stdio.h>
#include <stdint.h>
#include <tos/aes.h>
#include <tos/xbios.h>

static struct aes context;
static int magic_cookie;
static void identify_system(void)
{
    const uint32_t *cookie;
    __asm__ volatile ("move.l 0x5a0,%0" : "=a" (cookie) : : "memory");
    if (cookie) for (;cookie[0];cookie+=2)
        if (cookie[0]==0x4d616758UL) magic_cookie=1;
}

int main(void)
{
    FILE *report;
    int id,first,second;
    const char first_tail[128]={1,'1',0},second_tail[128]={1,'2',0};
    id=aes_appl_init(&context);
    if (id<0) return 1;
    xbios_supexec(identify_system);
    report=fopen("C:\\LAUNCH.LOG","w");
    if (!report) return 2;
    dprintf(fileno(report),"magic=%d launcher=%d\n",magic_cookie,id);
    if (!magic_cookie) { fclose(report); return 3; }
    /* MagiC SHW_PARALLEL=100 launches independent applications immediately. */
    first=aes_shel_write(&context,1,1,100,"C:\\COUNTER.PRG",first_tail);
    second=aes_shel_write(&context,1,1,100,"C:\\COUNTER.PRG",second_tail);
    dprintf(fileno(report),"first=%d second=%d\n",first,second);
    fclose(report);
    if (first<=0 || second<=0 || first==second) return 4;
    /* The desktop stays alive after either Counter exits. */
    for (;;) aes_evnt_timer(&context,500,0);
}
