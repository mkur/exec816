# Shared input.device

[Reference index](README.md) · [Low-level INPUT](input.md) · [Device I/O](device-io.md)

The installed subset admits unit zero/flags zero, QUERY and settled Close.
IM2 adds the Task/control/handler lifetime implementation. The boot controller
must explicitly start the selected input owner; opening alone does not start
a second owner alongside the existing console. ATTACH/DETACH require that
running service; otherwise they return IOERR_UNITBUSY. IM3 connects keyboard,
relative ST/port-2 pointer capture and synchronous route operations. QUERY
reports KEYBOARD_SET | POINTER_SET. The [migration plan](../plans/input-device-migration-plan.md) tracks
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
fixtures; production console startup remains unchanged.

ATTACH copies the 76-byte consumer descriptor and acquires the requested source
in the input Task. The service supplies configuration version/source/wake mask;
the consumer supplies generic keyboard flags and raw-key filters. A source-set
failure unwinds its acquired prefix. DETACH releases the source in its acquiring
Task; a later attach can choose new filters and gets a fresh capture generation.
For pointer capture supply POINTER_RELATIVE, POINTER_ST/POINTER_PORT and zero
initial coordinates/bounds. Relative movement/buttons carry the existing INPUT
event semantics; screen coordinates, acceleration and cursor drawing are consumer
responsibilities. Pointer-only attachment does not acquire the keyboard.

CREATE_ROUTE/PUBLISH_ROUTE/RETIRE_ROUTE/DISCARD name the INPUT source ID in
Request.source. CREATE_ROUTE uses routeFlags and returns the tag in route;
the others consume route. They complete synchronously with ordinary INPUT
status values in io_Error. Publication under an existing Task publication guard
does not wait for the input Task. Route zero stops addressed capture, old records
retain captured tags, and retirement can return BUSY. No event queue is added
between native INPUT and the bounded handler. Source acquisition, loss and
durable cancellation retain the [INPUT contract](input.md).
