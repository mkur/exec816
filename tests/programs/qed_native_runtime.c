/* Real native ownership and upstream text-store code; UI notifications below
 * belong only to this fixture. No donor startup/termination code is linked. */
#include "qed-runtime.h"
#include <exec816/c-runtime.h>
#include "global.h"
#include "memory.h"
#include <stdlib.h>
#include <string.h>
#include <exec816/program.h>

static int acquisitionBudget=-1;
static UWORD notifications;
static const char growth[900]={0};
APTR EXEC_CALL QedFixtureAlloc(ULONG bytes,ULONG attributes)
{
    if (!acquisitionBudget) return NULL;
    if (acquisitionBudget>0) --acquisitionBudget;
    return AllocMem(bytes,attributes);
}
short note(short def,short undo,short index) { ++notifications;return 1; }
short inote(short def,short undo,short index,short value) { ++notifications;return 1; }
void debug(char *format,...) { ++notifications; }
/* Syntax highlighting is deferred; these fixture callbacks never draw. */
void hl_insert(RINGP ring,LINEP line) {}
void hl_remove(RINGP ring,LINEP line) {}
void hl_update_zeile(RINGP ring,LINEP line) {}

static int text(void)
{
    RINGP ring=calloc(1,sizeof(*ring));
    LINEP line,extra,before;
    int n;
    if (!ring) return 101;
    init_memory();acquisitionBudget=0;
    if (init_textring(ring)) return 102;
    kill_textring(ring);kill_memory();
    acquisitionBudget=-1;init_memory();
    if (!init_textring(ring)) return 103;
    line=FIRST(ring);
    if (!INSERT(&line,0,5,"alpha") || !INSERT(&line,2,3,"XYZ") ||
        line->len!=8 || strcmp(TEXT(line),"alXYZpha")) return 104;
    if (!REALLOC(&line,2,-3) || strcmp(TEXT(line),"alpha")) return 105;
    extra=new_col("beta",4);
    if (!extra) return 106;
    col_append(ring,extra);
    if (ring->lines!=2 || textring_bytes(ring)!=10 ||
        strcmp(TEXT(FIRST(ring)),"alpha") || strcmp(TEXT(LAST(ring)),"beta")) return 107;
    /* Fill the current donor block, then refuse every new backing acquisition. */
    acquisitionBudget=0;
    for (n=0;n<128;++n) {
        extra=new_col("",0);
        if (!extra) break;
        col_append(ring,extra);
        if (!REALLOC(&extra,0,900)) break;
        memset(TEXT(extra),'q',900);TEXT(extra)[900]=0;
    }
    if (n==128) return 108;
    before=line;
    if (INSERT(&line,3,895,(char *)growth) || (ULONG)line!=(ULONG)before ||
        line->len!=5 || strcmp(TEXT(line),"alpha")) return 109;
    if (ist_mem_frei() || !notifications) return 110;
    acquisitionBudget=-1;
    kill_textring(ring);kill_textring(ring);kill_memory();kill_memory();
    free(ring);
    return 0;
}

static int body(int argc,char **argv)
{
    unsigned char *block;
    LONG largest;
    int result;
    if (argc!=2 || strcmp(argv[0],"PROBE.APP") || strcmp(argv[1],ExecGetArgStr()) || argv[2]) return 111;
    largest=Malloc(-1L);block=(void *)Malloc(largest);
    if (!block || largest<=52408L || ((ULONG)block&7) ||
        ((ULONG)block>>16)!=(((ULONG)block+largest-1)>>16)) return 120;
    Mfree(block);
    result=text();
    if (!malloc(37) || !calloc(3,21)) return 124;
    if (result) return result;
    if (argv[1][0]=='S') {
        WORD window,message[8];
        char *title=malloc(37);
        if (!title) return 129;
        strcpy(title,"Owned runtime stop");
        window=wind_create(NAME|CLOSER|MOVER,0,0,128,64);
        if (window<0 || !wind_set_str(window,WF_NAME,title) ||
            !wind_open(window,32,32,128,64)) return 130;
        do { if (!evnt_mesag(message)) return 131; } while (message[0]!=WM_CLOSED);
        if (!wind_close(window) || !wind_delete(window)) return 132;
    }
    return 0;
}

#define main QedProcessScenario
#include "c_process.c"
#undef main
int main(int argc,char **argv)
{
    struct QedHeapStats initial,stats;
    int result;
    QedHeapSnapshot(&initial);
    result=body(argc,argv);
    if (result) return result;
    QedHeapSnapshot(&stats);
    if (stats.blocks!=initial.blocks+(argv[1][0]=='S' ? 3:2) ||
        stats.payload!=initial.payload+(argv[1][0]=='S' ? 137:100) ||
        stats.backing!=initial.backing+(argv[1][0]=='S' ? 137+3*EXEC_CRT_ALLOCATION_PREFIX:100+2*EXEC_CRT_ALLOCATION_PREFIX) ||
        stats.peakBacking!=initial.backing+EXEC_CRT_MAX_ALLOCATION+EXEC_CRT_ALLOCATION_PREFIX) return 126;
    if (ExecGetArgStr()[0]=='S') return -124;
    return QedProcessScenario();
}
