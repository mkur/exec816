/* SPDX-License-Identifier: MIT */
#include "counter.h"

struct Counter GEMCounter;
static const struct CounterConfig config={"Counter",192,32,208,104,4,0};

int main(void)
{
    GEMCounter.config=&config;
    return CounterRun(&GEMCounter);
}
