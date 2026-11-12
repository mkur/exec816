/* SPDX-License-Identifier: MIT
 * Resource-free desktop for the original viewer and an independent Counter. */
#include <stdio.h>
#include <stdint.h>
#include <tos/aes.h>
#include <tos/xbios.h>

static struct aes context;
static int magic;
/* Keytbl retains these pointers. The desktop outlives both child processes. */
static char keys[3][128];
static void identify(void)
{
    const uint32_t *cookie;
    __asm__ volatile ("move.l 0x5a0,%0" : "=a" (cookie) : : "memory");
    if (cookie) for (;cookie[0];cookie+=2)
        if (cookie[0]==0x4d616758UL) magic=1;
}
int main(void)
{
    FILE *report,*keymap;
    int id,counter,text;
    const char counter_tail[128]={1,'2',0};
    const char text_tail[128]={13,'S','Y','S',':','S','T','O','R','Y','.','T','X','T',0};
    id=aes_appl_init(&context);
    if (id<0) return 1;
    xbios_supexec(identify);
    report=fopen("C:\\LAUNCH.LOG","w");
    if (!report) return 2;
    dprintf(fileno(report),"magic=%d launcher=%d\n",magic,id);
    if (!magic) {fclose(report);return 3;}
    keymap=fopen("C:\\USKEYS.SYS","r");
    if (!keymap || fread(keys,1,sizeof(keys),keymap)!=sizeof(keys)) {
        if (keymap) fclose(keymap);
        fclose(report);aes_appl_exit(&context);return 5;
    }
    fclose(keymap);
    xbios_keytbl(keys[0],keys[1],keys[2]);
    dprintf(fileno(report),"keyboard=us\n");
    counter=aes_shel_write(&context,1,1,100,"C:\\COUNTER.PRG",counter_tail);
    text=aes_shel_write(&context,1,1,100,"C:\\TEXT.PRG",text_tail);
    dprintf(fileno(report),"counter=%d text=%d\n",counter,text);
    fclose(report);
    if (counter<=0 || text<=0 || counter==text) return 4;
    for (;;) aes_evnt_timer(&context,500,0);
}
