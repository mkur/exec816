/* SPDX-License-Identifier: MIT */
#include "../gem-counter/counter.h"

struct Counter GEMCounter;
static const struct CounterConfig configs[]={
    {"Counter / paint",376,40,216,72,1,0,100,0},
    {"Counter / silent",376,40,216,72,1,0,100,1}
};

int main(int argc,char **argv)
{
    GEMCounter.config=&configs[argc>1 && argv[1][0]=='s' ? 1:0];
    return CounterRun(&GEMCounter);
}
