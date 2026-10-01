#include <exec/display.h>
__attribute__((section("exec_layout")))
const unsigned short __exec_layout[] = {
    sizeof(struct DisplayLease),
    offsetof(struct DisplayLease, owner),
    offsetof(struct DisplayLease, generation),
    offsetof(struct DisplayLease, kind),
    offsetof(struct DisplayLease, state),
    offsetof(struct DisplayLease, reserved),
};
