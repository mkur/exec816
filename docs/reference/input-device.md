# Shared input.device

[Reference index](README.md) · [Low-level INPUT](input.md) · [Device I/O](device-io.md)

The IM1 installed subset admits unit zero/flags zero, QUERY and settled Close.
Capture, handler registration and route commands are not implemented yet and
return IOERR_NOCMD. QUERY reports zero source capabilities until capture is
connected. The [migration plan](../plans/input-device-migration-plan.md) tracks
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
collection. There is no hardware capture or additional Task in this slice.
