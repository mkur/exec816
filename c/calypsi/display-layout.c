#include <exec/display.h>
__attribute__((section("exec_layout")))
const unsigned short __exec_layout[] = {
    sizeof(struct DisplayLease),
    offsetof(struct DisplayLease, owner),
    offsetof(struct DisplayLease, generation),
    offsetof(struct DisplayLease, kind),
    offsetof(struct DisplayLease, state),
    offsetof(struct DisplayLease, reserved),
    sizeof(struct DisplayGrant),
    offsetof(struct DisplayGrant, task),
    offsetof(struct DisplayGrant, mask),
    offsetof(struct DisplayGrant, owner),
    offsetof(struct DisplayGrant, generation),
    offsetof(struct DisplayGrant, state),
    offsetof(struct DisplayGrant, slot),
    offsetof(struct DisplayGrant, reserved),
};
