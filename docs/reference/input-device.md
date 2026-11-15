# Shared input.device

[Reference index](README.md) · [Low-level INPUT](input.md) · [Device I/O](device-io.md)

The installed subset admits unit zero/flags zero, QUERY and settled Close.
IM2 adds the Task/control/handler lifetime implementation. The boot controller
must explicitly start the selected input owner; opening alone does not start
a second owner alongside the existing console. ATTACH/DETACH require that
running service; otherwise they return IOERR_UNITBUSY. The production capture
adapter is not connected yet and rejects attach with INPUT.UNSUPPORTED.
Route commands still return IOERR_NOCMD. QUERY reports zero source capabilities
until capture is connected. The [migration plan](../plans/input-device-migration-plan.md) tracks
remaining work; its target semantics are not an installed-service claim.

Use the generated [InputDeviceRequest](../../c/include/devices/input.h), a
50-byte record with the IOStdReq prefix and source/route fields. The Action!
records are in INPUTDEVICE. QUERY uses io_Data/io_Length for a 12-byte
InputDeviceCapabilities buffer and reports its size in io_Actual. Short buffers
return IOERR_BADLENGTH. Version is one, the consumer descriptor is 76 bytes,
captured events use the existing 24-byte INPUT record and route capacity is
sixteen per source. Unsupported commands return IOERR_NOCMD.

The public C wire descriptor stores a full native handler entry address as
ULONG. Its callback convention is Action native-v2, with LONGCARD context and
borrowed INPUT.Event pointer, and no result. An ordinary C function pointer is
not that ABI. Generic C device control uses the standard I/O bridge; a direct
C callback adapter is not supplied by this subset.

Open validates the complete request extent and retains its caller. After open,
request/data storage lifetime and settled Close are caller obligations. Quick
completion sends no reply; every non-quick submission replies once and requires
collection. Each open permits one pending attach/detach control; another returns
IOERR_UNITBUSY. Queued controls clear QUICK. Abort before commitment leaves the
registration unchanged; completed attach requires explicit detach. Detach
acknowledges after callback/source retirement. Close requires a detached binding.

The service Task uses signals and an owned request port, sleeps while idle and
calls bounded handlers without a driver guard. It never calls AES or draws.
Stop refuses live opens. This slice starts the Task only in isolated service
fixtures; production console startup and physical ownership remain unchanged.
