/* Private ordinary C/native bridge. The admitted display driver owns lifetime.
 * Arm/State/Reset run only after admission in the current driver invocation. */
#ifndef EXEC_VBXE_NOTIFY_H
#define EXEC_VBXE_NOTIFY_H
#include <exec/display.h>
#define VBXE_NOTIFY_ARMED 1
#define VBXE_NOTIFY_DONE 2
#define VBXE_NOTIFY_EXPIRED 3
UWORD VbxeNotifyOpen(struct DisplayLease *lease);
UWORD VbxeNotifyClose(struct DisplayLease *lease);
ULONG VbxeNotifyMask(struct DisplayLease *lease);
UWORD VbxeNotifyArm(ULONG id);
UWORD VbxeNotifyState(ULONG id);
void VbxeNotifyReset(void);
#endif
