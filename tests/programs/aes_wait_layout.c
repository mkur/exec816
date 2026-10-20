#include <exec816/aes-wait.h>
#include <stddef.h>
__attribute__((section("exec_layout")))
const unsigned short AESWaitLayout[]={
    sizeof(struct ExecAESWaitSpec),offsetof(struct ExecAESWaitSpec,flags),
    offsetof(struct ExecAESWaitSpec,buttonClicks),offsetof(struct ExecAESWaitSpec,buttonMask),
    offsetof(struct ExecAESWaitSpec,buttonState),offsetof(struct ExecAESWaitSpec,m1Flags),
    offsetof(struct ExecAESWaitSpec,m1X),offsetof(struct ExecAESWaitSpec,m1Y),
    offsetof(struct ExecAESWaitSpec,m1Width),offsetof(struct ExecAESWaitSpec,m1Height),
    offsetof(struct ExecAESWaitSpec,milliseconds),offsetof(struct ExecAESWaitSpec,signalMask),
    offsetof(struct ExecAESWaitSpec,received),offsetof(struct ExecAESWaitSpec,message),
    offsetof(struct ExecAESWaitSpec,mouseX),offsetof(struct ExecAESWaitSpec,mouseY),
    offsetof(struct ExecAESWaitSpec,mouseButtons),offsetof(struct ExecAESWaitSpec,keyState),
    offsetof(struct ExecAESWaitSpec,key),offsetof(struct ExecAESWaitSpec,clicks)
};
