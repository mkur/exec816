# Shared input.device

[Reference index](README.md) · [Low-level INPUT](input.md) · [Device I/O](device-io.md)

`input.device` provides shared keyboard and relative ST/port-2 capture through
ordinary Exec device requests. It admits unit zero/flags zero, QUERY, consumer
attach/detach and synchronous route control. The selected console startup starts
the service before its display frontend; Open/query alone does not create a Task.
ATTACH/DETACH require that running service and otherwise return IOERR_UNITBUSY.
QUERY reports KEYBOARD_SET | POINTER_SET. See the
[migration record](../history/input-device-migration.md) for development evidence.

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
Stop refuses live opens. Console startup starts the shared input service before
the selected display frontend and backend. Standard text attaches keyboard alone; GEM attaches the
keyboard and relative pointer through public device handles. The extracted AES
consumer resolves copied AESSNAPSHOT routes and publishes application inboxes
without UPDATE or scene access. Native menu/drag interactions enter guarded
copied queues for the manager; pointer normalization occurs once in the
consumer and physical cursor drawing stays in the frontend. A retained manager
press carries the captured window identity/epoch and holds its endpoint until
consumption or cancellation. Withdrawal and overflow retire those holds;
endpoint close rejects new holds before checking publisher drainage.
An asynchronous system stop closes new admission while allowing existing
consumers to detach. The worker retires only after those bindings close.

Handlers run synchronously in the input Task with no driver guard. They may
copy/translate input, publish inboxes and signal readiness. They must not Wait,
obtain UPDATE/MCTRL, draw, enter a physical grant or call application
callbacks. Short consumer publication guards remain necessary. Callback state
must be initialized before ATTACH: delivery can begin before its caller resumes.

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
retain captured tags, and exhaustion/retirement can return BUSY. No event queue is added
between native INPUT and the bounded handler. Source acquisition, loss and
durable cancellation retain the [INPUT contract](input.md).

## Native client convenience calls

[INPUTCLIENT](../../lib/input/inputclient.act) provides an opaque handle over
the public device protocol. Open creates the owner Task's port/control request;
Attach and Detach use ordinary DoIO/collection. Close requires a detached handle
and quiesced shared callers, then releases the binding, requests and port.

CreateRoute/PublishRoute/RetireRoute/Discard use a separate borrowed quick
request, serialized with short Forbid sections. They can run in cooperating
Tasks without waiting on the owner's reply port. They grant no capture Take
authority and do not expose the driver's private INPUT lease. Handles and their
complete lifetime remain caller-owned, as with other Exec resources.

## Resources and limits

The service reserves a 1,024-byte upper-RAM arena, including unused capacity,
with four open bindings and two source records. This changes no fixed, root,
kernel, idle or per-Task bank-zero reservation. Selected startup occupies three
service Task pools: input, console backend and display frontend. Compared with
the former combined console/input owner it occupies one additional ordinary
pool (1,600 bytes: 1,312 stack, 256 DP and 32 guard bytes). The existing large GUI
frontend pool remains reserved at 2,848 bytes. The eight-pool map is unchanged.

Each native client handle owns 133 bytes of request/port/state objects before
heap overhead; GEM uses separate keyboard and pointer handles. Retained manager
targets add 192 bytes to the GUI service allocation; standard text has no AES
allocation. Close/detach remain cooperative. Code/state must stay live through
detach acknowledgment and consumer-side copied-event retirement. Forced consumer
exit/unload recovery, direct ordinary C callbacks, live GEM/text switching and
the future VBXE text-mode renderer are not supplied. The existing standalone
bitmap startup remains supported. SCRENMGR's SM3/SM4 migration is separate.
