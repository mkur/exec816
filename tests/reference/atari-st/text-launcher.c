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
#ifdef REFERENCE_MGVIEW
    const char text_tail[128]={12,'A',':','\\','S','T','O','R','Y','.','T','X','T',0};
    const char *program="A:\\MGVIEW.APP";
#else
    const char text_tail[128]={13,'S','Y','S',':','S','T','O','R','Y','.','T','X','T',0};
    const char *program="C:\\TEXT.PRG";
#endif
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
#ifdef REFERENCE_SCROLL_COMPARE
    (void)counter_tail;
    counter=0;
#else
    counter=aes_shel_write(&context,1,1,100,"C:\\COUNTER.PRG",counter_tail);
#endif
    text=aes_shel_write(&context,1,1,100,program,text_tail);
    dprintf(fileno(report),"counter=%d text=%d\n",counter,text);
#ifdef REFERENCE_MGVIEW
    if (text>0) {
        int attempt;
        int16_t window,owner,x,y,w,h;
        for (attempt=0;attempt<300;++attempt) {
            aes_evnt_timer(&context,100,0);
            if (aes_wind_get(&context,0,10,&window,&x,&y,&w) && window>0 &&
                aes_wind_get(&context,window,20,&owner,&x,&y,&w) && owner==text) {
                aes_evnt_timer(&context,200,0);
                aes_wind_get(&context,window,4,&x,&y,&w,&h);
                dprintf(fileno(report),"ready viewer=%d window=%d work=%d,%d,%d,%d\n",
                    text,window,x,y,w,h);
                break;
            }
        }
    }
#endif
    fclose(report);
#ifdef REFERENCE_SCROLL_COMPARE
    if (text<=0) return 4;
#else
    if (counter<=0 || text<=0 || counter==text) return 4;
#endif
    for (;;) aes_evnt_timer(&context,500,0);
}
