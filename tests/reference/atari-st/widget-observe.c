/* SPDX-License-Identifier: MIT
 * Startup addresses and final results only. During interaction the host reads
 * guest memory; this wrapper does no periodic logging or timed drawing I/O. */
#include <stdio.h>
#include "examples/gem-widget/widget.h"
#include "examples/gem-counter/counter.h"

#ifdef SAMPLE_WIDGET
extern struct Widget GEMWidget;
#define APP GEMWidget
#define REPORT "C:\\WIDGET.LOG"
#else
extern struct Counter GEMCounter;
#define APP GEMCounter
#define REPORT "C:\\PULSE.LOG"
#endif
static WORD reported;

#define WAIT_PARAMETERS \
    WORD f,WORD bc,WORD bm,WORD bs,WORD f1,WORD x1,WORD y1,WORD w1,WORD h1, \
    WORD f2,WORD x2,WORD y2,WORD w2,WORD h2,WORD *msg,WORD lo,WORD hi, \
    WORD *mx,WORD *my,WORD *mb,WORD *ks,WORD *kr,WORD *br
#define WAIT_ARGUMENTS f,bc,bm,bs,f1,x1,y1,w1,h1,f2,x2,y2,w2,h2,msg,lo,hi,mx,my,mb,ks,kr,br
WORD __real_evnt_multi(WAIT_PARAMETERS);
WORD __wrap_evnt_multi(WAIT_PARAMETERS)
{
    FILE *file;
    if (!reported && APP.ready) {
        reported=1;
        file=fopen(REPORT,"w");
        if (file) {
            dprintf(fileno(file),"id=%d window=%d ready=%lx paints=%lx work=%lx ",
                APP.id,APP.window,(unsigned long)&APP.ready,
                (unsigned long)&APP.paints,(unsigned long)APP.work);
#ifdef SAMPLE_WIDGET
            dprintf(fileno(file),"actions=%lx tree=%lx label=%lx\n",
                (unsigned long)&APP.actions,(unsigned long)APP.tree,(unsigned long)APP.label);
#else
            dprintf(fileno(file),"count=%lx period=%u silent=%u\n",
                (unsigned long)&APP.count,APP.config->periodMs,APP.config->silent);
#endif
            fclose(file);
        }
    }
    return __real_evnt_multi(WAIT_ARGUMENTS);
}

int __real_main(int argc,char **argv);
int __wrap_main(int argc,char **argv)
{
    FILE *file;
    int result=__real_main(argc,argv);
    file=fopen(REPORT,"a");
    if (file) {
        dprintf(fileno(file),"exit=%d ready=%d opened=%d window=%d vdi=%d paints=%lu\n",
            result,APP.ready,APP.opened,APP.window,APP.vdi,(unsigned long)APP.paints);
        fclose(file);
    }
    return result;
}
