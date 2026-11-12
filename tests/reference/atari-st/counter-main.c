/* SPDX-License-Identifier: MIT
 * ST startup and observation around the unchanged Counter application body. */
#include <stdio.h>
#include "examples/gem-counter/counter.h"

struct Counter GEMCounter;
#ifndef REFERENCE_COUNTER_SECOND_Y
#define REFERENCE_COUNTER_SECOND_Y 192
#endif
static const struct CounterConfig configs[]={
    {"Counter 1",48,64,232,64,1,0},
    {"Counter 2",360,REFERENCE_COUNTER_SECOND_Y,232,64,1,0}
};
static FILE *report;
static uint32_t reported=0xffffffffUL;

/* GNU ld interposes only the event wait. Observation happens after the previous
 * iteration has painted and released UPDATE, before the next wait. */
#define WAIT_PARAMETERS \
    WORD f,WORD bc,WORD bm,WORD bs,WORD f1,WORD x1,WORD y1,WORD w1,WORD h1, \
    WORD f2,WORD x2,WORD y2,WORD w2,WORD h2,WORD *msg,WORD lo,WORD hi, \
    WORD *mx,WORD *my,WORD *mb,WORD *ks,WORD *kr,WORD *br
#define WAIT_ARGUMENTS f,bc,bm,bs,f1,x1,y1,w1,h1,f2,x2,y2,w2,h2,msg,lo,hi,mx,my,mb,ks,kr,br
WORD __real_evnt_multi(WAIT_PARAMETERS);
WORD __wrap_evnt_multi(WAIT_PARAMETERS)
{
    WORD top,a,b,c;
    if (GEMCounter.ready && reported!=GEMCounter.count) {
        reported=GEMCounter.count;
        wind_get(0,WF_TOP,&top,&a,&b,&c);
        dprintf(fileno(report),"count=%lu paints=%lu id=%d window=%d top=%d work=%d,%d,%d,%d\n",
            (unsigned long)GEMCounter.count,(unsigned long)GEMCounter.paints,
            GEMCounter.id,GEMCounter.window,top,GEMCounter.work[0],GEMCounter.work[1],
            GEMCounter.work[2],GEMCounter.work[3]);
    }
    return __real_evnt_multi(WAIT_ARGUMENTS);
}

int main(int argc,char **argv)
{
    int instance,result;
    if (argc!=2 || (argv[1][0]!='1' && argv[1][0]!='2')) return 10;
    instance=argv[1][0]-'1';
    GEMCounter.config=&configs[instance];
    report=fopen(instance ? "C:\\COUNT2.LOG":"C:\\COUNT1.LOG","w");
    if (!report) return 11;
    dprintf(fileno(report),"instance=%d\n",instance+1);
    result=CounterRun(&GEMCounter);
    dprintf(fileno(report),"exit=%d count=%lu paints=%lu\n",result,
        (unsigned long)GEMCounter.count,(unsigned long)GEMCounter.paints);
    fclose(report);
    return result;
}
