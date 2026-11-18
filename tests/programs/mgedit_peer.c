/* SPDX-License-Identifier: MIT */
#include <gem.h>

volatile UWORD peerProgress,peerStop;

int main(void)
{
    while (!peerStop) {
        if (!evnt_timer(20,0)) return 1;
        ++peerProgress;
    }
    return 0;
}
