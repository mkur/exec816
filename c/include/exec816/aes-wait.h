/* Generated from abi/aes-wait.json; do not edit. */
#ifndef EXEC816_AES_WAIT_H
#define EXEC816_AES_WAIT_H
#include <exec/types.h>
#define MU_EXEC 0x8000U
struct ExecAESWaitSpec {
    UWORD flags;
    WORD buttonClicks;
    WORD buttonMask;
    WORD buttonState;
    WORD m1Flags;
    WORD m1X;
    WORD m1Y;
    WORD m1Width;
    WORD m1Height;
    ULONG milliseconds;
    ULONG signalMask;
    ULONG received;
    WORD message[8];
    WORD mouseX;
    WORD mouseY;
    WORD mouseButtons;
    WORD keyState;
    WORD key;
    WORD clicks;
};
WORD ExecAESWait(struct ExecAESWaitSpec *spec);
#endif
