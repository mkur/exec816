/* SPDX-License-Identifier: MIT
 * Resource-free MagiC desktop. CASE.TXT chooses solo, silent or paint at boot. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <tos/aes.h>
#include <tos/xbios.h>

static struct aes context;
static int16_t magic;
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
    FILE *file;
    int id,counter=0,widget,i;
    struct aes_mesag message;
    char mode[16]={0},tail[128]={0};
    const char empty[128]={0};
    id=aes_appl_init(&context);
    if (id<0) return 1;
    xbios_supexec(identify);
    if (!magic) return 2;
    file=fopen("C:\\CASE.TXT","r");
    if (!file) return 3;
    fread(mode,1,sizeof(mode)-1,file);
    fclose(file);
    for (i=0;mode[i];++i)
        if (mode[i]=='\r' || mode[i]=='\n') {mode[i]=0;break;}
    if (strcmp(mode,"solo") && strcmp(mode,"silent") && strcmp(mode,"paint")) return 4;
    file=fopen("C:\\USKEYS.SYS","r");
    if (!file) return 5;
    if (fread(keys,1,sizeof(keys),file)!=sizeof(keys)) {fclose(file);return 6;}
    fclose(file);
    xbios_keytbl(keys[0],keys[1],keys[2]);
    if (strcmp(mode,"solo")) {
        tail[0]=(char)strlen(mode);
        strcpy(tail+1,mode);
        counter=aes_shel_write(&context,1,1,100,"C:\\PULSE.PRG",tail);
        if (counter<=0) return 7;
    }
    widget=aes_shel_write(&context,1,1,100,"C:\\WIDGET.PRG",empty);
    file=fopen("C:\\LAUNCH.LOG","w");
    if (!file) return 8;
    dprintf(fileno(file),"magic=%d launcher=%d mode=%s counter=%d widget=%d\n",
        magic,id,mode,counter,widget);
    fclose(file);
    if (widget<=0 || widget==counter) return 9;
    /* No periodic desktop wakeups compete with the measured applications. */
    for (;;) aes_evnt_mesag(&context,&message);
}
