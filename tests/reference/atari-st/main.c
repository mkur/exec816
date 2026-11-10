/* SPDX-License-Identifier: MIT */
#include <stdio.h>
#include <string.h>
#include <tos/xbios.h>
#include "examples/gem-counter/counter.c"

/* The three functions in workload.inc are extracted verbatim from the native
 * baseline. Only startup, SDK binding and observation differ on the ST. */
#define OBJECTS 33
#define REQUIRE(x) do { if (!(x)) return 0; } while (0)
static struct Counter MagicCounter;
static OBJECT MagicObjects[OBJECTS];
static WORD MagicObjectsCount,MagicVisibleCount;
static const struct CounterConfig config={"Exec/MagiC same source",32,24,480,184,4,3};
#include "workload.inc"

extern WORD reference_font[4];
volatile WORD reference_kind,reference_iteration,reference_done;
static volatile uint32_t ticks;
static WORD magic_cookie;

static void identify_system(void)
{
    const uint32_t *cookie;
    __asm__ volatile ("move.l 0x5a0,%0" : "=a" (cookie) : : "memory");
    if (cookie) for (;cookie[0];cookie+=2)
        if (cookie[0]==0x4d616758UL) magic_cookie=1; /* MagX */
}

/* The ST protects low memory even from a 68000 user-mode application. */
static void read_ticks(void)
{
    uint32_t value;
    __asm__ volatile ("move.l 0x4ba,%0" : "=d" (value) : : "memory");
    ticks=value;
}

static uint32_t clock_ticks(void)
{
    xbios_supexec(read_ticks);
    return ticks;
}

/* Stable symbol for Hatari profiling. Clock and file I/O stay outside it. */
__attribute__((noinline)) WORD ReferenceSample(void)
{
    return draw_objects();
}

int main(void)
{
    FILE *f;
    WORD i,j,cw,ch,bw,bh,status,mx,my,mb,ks,kr,br;
    uint32_t before,after;
    MagicCounter.config=&config;
    MagicCounter.id=appl_init();
    if (MagicCounter.id<0) return 1;
    MagicCounter.vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<11;++i) MagicCounter.input[i]=1;
    MagicCounter.input[6]=4;
    MagicCounter.input[9]=3;
    MagicCounter.input[10]=2;
    v_opnvwk(MagicCounter.input,&MagicCounter.vdi,MagicCounter.output);
    if (MagicCounter.vdi==0) return 2;
    MagicCounter.window=wind_create(NAME|CLOSER|MOVER,32,24,480,184);
    if (MagicCounter.window<0) return 3;
    wind_set_str(MagicCounter.window,WF_NAME,config.title);
    if (!wind_open(MagicCounter.window,32,24,480,184)) return 4;
    f=fopen("C:\\REPORT.TXT","w");
    if (!f) return 5;
    xbios_supexec(identify_system);
    dprintf(fileno(f),"AES id=%d screen=%d,%d colours=%d font=%d,%d,%d,%d clock=200 magic=%d\n",
        MagicCounter.id,MagicCounter.output[0]+1,MagicCounter.output[1]+1,
        MagicCounter.output[13],reference_font[0],reference_font[1],
        reference_font[2],reference_font[3],magic_cookie);
    for (i=0;i<3;++i) {
        reference_kind=i;
        work();
        object_tree(i);
        for (j=0;j<10;++j) {
            reference_iteration=j;
            before=clock_ticks();
            status=ReferenceSample();
            after=clock_ticks();
            dprintf(fileno(f),"case=%d sample=%d count=%d visible=%d okay=%d ticks=%ld work=%d,%d,%d,%d\n",
                i,j,MagicObjectsCount,MagicVisibleCount,status,(long)(after-before),
                MagicCounter.work[0],MagicCounter.work[1],MagicCounter.work[2],MagicCounter.work[3]);
            if (!status) { fclose(f); return 6; }
        }
    }
    fclose(f);
    reference_done=1;
    /* Keep the final tree visible. The bounded host runner quits Hatari; this
     * reference does not exercise normal window/application retirement. */
    for (;;) evnt_multi(MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
        MagicCounter.message,1000,0,&mx,&my,&mb,&ks,&kr,&br);
}
