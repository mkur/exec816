/* Real native ownership and upstream text-store code; UI notifications below
 * belong only to this fixture. No donor startup/termination code is linked. */
#include "qed-runtime.h"
#include "global.h"
#include "memory.h"
#include <stdlib.h>
#include <string.h>
#include <exec816/program.h>

static int acquisitionBudget=-1;
static UWORD notifications;
static const char growth[900]={0};
static char argumentLimit[257];
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
    if (ring->lines!=2 || textring_bytes(ring)!=11) return 107;
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
    unsigned char *block,*larger;
    LONG largest;
    char **parsed;
    int count,result;
    unsigned int n;
    if (argc!=2 || strcmp(argv[0],"PROBE.APP") || strcmp(argv[1],ExecGetArgStr()) || argv[2]) return 111;
    if (malloc(0) || calloc(0,7) || calloc((size_t)-1,2) || malloc(65529UL)) return 112;
    block=calloc(8,17);
    if (!block) return 113;
    for (n=0;n<136;++n) if (block[n]) return 114;
    memset(block,0xa7,136);acquisitionBudget=0;
    if (realloc(block,200)) return 115;
    for (n=0;n<136;++n) if (block[n]!=0xa7) return 116;
    acquisitionBudget=-1;larger=realloc(block,240);
    if (!larger) return 117;
    for (n=0;n<136;++n) if (larger[n]!=0xa7) return 118;
    if (realloc(larger,0)) return 119;
    largest=Malloc(-1L);block=(void *)Malloc(largest);
    if (!block) return 120;
    if (largest<=52408L) return 127;
    if (((ULONG)block>>16)!=(((ULONG)block+largest-1)>>16)) return 128;
    Mfree(block);
    if (!QedArguments("  \"RAM:space name\" \t","qed",&count,&parsed) || count!=2 ||
        strcmp(parsed[0],"qed") || strcmp(parsed[1],"RAM:space name") || parsed[2]) return 121;
    free(parsed);
    if (!QedArguments(" \t","qed",&count,&parsed) || count!=1 || parsed[1]) return 122;
    free(parsed);
    if (QedArguments("a b","qed",&count,&parsed) || parsed || count ||
        QedArguments("\"unfinished","qed",&count,&parsed)) return 123;
    memset(argumentLimit,'p',255);argumentLimit[255]=0;
    if (!QedArguments(argumentLimit,"qed",&count,&parsed) || count!=2 ||
        strlen(parsed[1])!=255) return 133;
    free(parsed);argumentLimit[255]='p';argumentLimit[256]=0;
    if (QedArguments(argumentLimit,"qed",&count,&parsed) || parsed || count) return 134;
    result=text();
    /* Leave owned objects for the ordinary entry cleanup, including realloc. */
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
        /* The borrowed title is reachable until the window retires. Entry
         * cleanup now owns its release; shared AES teardown follows return. */
    }
    return 0;
}

#define main QedProcessScenario
#include "c_process.c"
#undef main
int main(void)
{
    struct QedHeapStats stats;
    int result;
    acquisitionBudget=0;
    if (QedRuntimeRun(body)!=20) return 125;
    acquisitionBudget=-1;
    result=QedRuntimeRun(body);
    QedHeapSnapshot(&stats);
    if (result) return result;
    if (stats.blocks || stats.payload || stats.backing || stats.peakBacking!=65572UL) return 126;
    if (ExecGetArgStr()[0]=='S') return -124;
    return QedProcessScenario();
}
