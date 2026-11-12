/* SPDX-License-Identifier: MIT
 * MagiC startup and observation around the unchanged original text viewer. */
#include <stdio.h>
#include <string.h>
#include <tos/gemdos.h>
#include "examples/gem-text/text.h"

struct TextApp GEMText;
static FILE *report;
static ULONG paints=~0UL,bytes=~0UL;
static WORD first=-1,phase=-1;
static char status[81];
#ifdef REFERENCE_SCROLL_COMPARE
static WORD startup_complete;
#endif
void reference_arguments(const char *);
void reference_resources(FILE *);
extern WORD reference_update_depth;
void reference_selector(WORD result,WORD button,const char *file)
{
    dprintf(fileno(report),"selector result=%d button=%d depth=%d file=%s\n",
        result,button,reference_update_depth,file);
}

#define WAIT_PARAMETERS \
    WORD f,WORD bc,WORD bm,WORD bs,WORD f1,WORD x1,WORD y1,WORD w1,WORD h1, \
    WORD f2,WORD x2,WORD y2,WORD w2,WORD h2,WORD *msg,WORD lo,WORD hi, \
    WORD *mx,WORD *my,WORD *mb,WORD *ks,WORD *kr,WORD *br
#define WAIT_ARGUMENTS f,bc,bm,bs,f1,x1,y1,w1,h1,f2,x2,y2,w2,h2,msg,lo,hi,mx,my,mb,ks,kr,br
WORD __real_evnt_multi(WAIT_PARAMETERS);
WORD __wrap_evnt_multi(WAIT_PARAMETERS)
{
    if (GEMText.ready &&
#ifdef REFERENCE_SCROLL_COMPARE
        !startup_complete &&
#endif
        (paints!=GEMText.paints || first!=GEMText.first ||
        phase!=GEMText.load.phase || bytes!=GEMText.load.candidate.bytes ||
        strcmp(status,GEMText.status))) {
        paints=GEMText.paints;first=GEMText.first;phase=GEMText.load.phase;
        bytes=GEMText.load.candidate.bytes;strcpy(status,GEMText.status);
        dprintf(fileno(report),"state id=%d window=%d first=%d rows=%d columns=%d lines=%u "
            "bytes=%lu phase=%d read=%lu dirty=%d paints=%lu loads=%lu "
            "work=%d,%d,%d,%d status=%s\n",
            GEMText.id,GEMText.window,first,GEMText.rows,GEMText.columns,GEMText.document.lines,
            (unsigned long)GEMText.document.bytes,phase,(unsigned long)bytes,GEMText.dirty,
            (unsigned long)paints,(unsigned long)GEMText.loads,
            GEMText.work[0],GEMText.work[1],GEMText.work[2],GEMText.work[3],status);
#ifdef REFERENCE_SCROLL_COMPARE
        if (GEMText.loads && !GEMText.load.phase && !GEMText.dirty) startup_complete=1;
#endif
    }
    return __real_evnt_multi(WAIT_ARGUMENTS);
}

int main(int argc,char **argv)
{
    int result;
    if (argc>2 || (argc==2 && strlen(argv[1])>127)) return 10;
    reference_arguments(argc==2 ? argv[1]:"");
    report=fopen("C:\\TEXT.LOG","w");
    if (!report) return 11;
    /* Native selector bookkeeping must use a native drive as well as its path. */
    gemdos_dsetdrv(0);
    result=TextRun(&GEMText);
    dprintf(fileno(report),"exit=%d paints=%lu loads=%lu\n",result,
        (unsigned long)GEMText.paints,(unsigned long)GEMText.loads);
    reference_resources(report);
    fclose(report);
    return result;
}
