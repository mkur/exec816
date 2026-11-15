# input.device implementation contract

[Migration plan](input-device-migration-plan.md) · [Design](input-device-design.md)

IM0, 2026-11-15. The user's request to implement the reviewed migration plan
selects its separate frontend proposal. Reuse the existing console/system
execution capacity for input; retain CONSOLEBACKEND; admit one active frontend
context for standard text, standalone bitmap or GUI startup. This adds one
occupied Task slot. No stack/DP pool or fixed bank-zero reservation is enlarged.
The frontend retains the old role's stack class until measured; input handler
depth is measured separately. Task metadata and device state live in upper RAM.

## Execution and retirement

| Owner | Work and retirement boundary |
| --- | --- |
| input.device Task | Source Acquire/Take/Release, source configuration changes, queued attach/detach, bounded native handler dispatch. No GUI/display imports. |
| Console backend | Existing request/model and translated ingress quanta. DOS keeps cooked editing. No drawing or UPDATE waits. |
| Active frontend | Text/bitmap display lifetime, copied views and physical retirement; GUI mode also runs the existing manager loop until SM3/SM4 replace it. Retire owned DMA and queued display access before a blocking UPDATE Obtain. |
| AES consumer | Copied routing and inbox publication in the input Task. Manager interaction is copied to the frontend. Consumer-owned endpoints remain pinned until copied events retire. |
| Applications | Existing synchronous AES/VDI drawing and delegated-grant completion. No foreign Task obtains an application's UPDATE to finish its operation. |

Cold startup admits input, backend and selected frontend independently and
publishes each readiness only after its resources exist. Console/AES close
detaches its consumer; the input service remains resident. Explicit system
shutdown retires frontend/consumer references, backend work and source captures
before their owning Tasks release storage/signals. Source configuration changes
require retirement/reacquisition in the input Task; INPUT's immutable acquired
configuration is never edited behind its producer.

## Public profile

Version 1 uses unit zero, flags zero and ordinary device requests. Sources are
a keyboard/pointer interest mask; route operations name existing INPUT source
IDs. Commands are QUERY, ATTACH, DETACH, CREATE_ROUTE, PUBLISH_ROUTE,
RETIRE_ROUTE and DISCARD. No event injection, handler chain or polling API.

The generated InputRequest has a complete IOStdReq prefix plus source/route
flags and a 32-bit capture route. QUERY copies a version/capabilities/limits
record. ATTACH copies a versioned handler descriptor containing a source mask,
full-width handler/context values and generic keyboard/pointer configurations.
The service replaces wake masks with its own allocated signals. Relative pointer
mode and low-level filter/route semantics remain unchanged.

Handler execution uses the Action native-v2 ABI: no result, a LONGCARD context
and borrowed INPUT.Event pointer, on the input Task's own DP/stack. C wire
records preserve full addresses until admission and describe the native entry
explicitly; an ordinary C function pointer must not be mistaken for a native
entry. Any C callback adapter needs its own emitted calling-convention proof
before exposure. Generic C control uses the existing device I/O bridge.

Attach/detach clear QUICK when queued. Before commitment AbortIO leaves the
registration unchanged; after commitment normal completion wins. Every
non-quick control request replies once. Detach acknowledges only after the last
callback and device-owned capture/route references retire. Consumers separately
drain copied downstream events before freeing their own state. Close requires
detached, collected bindings; it never waits inside the caller dispatch guard.

Route publication completes without waiting, under the consumer's copied
publication guard and existing native capture transaction. Old records keep
their capture tags. Exhaustion and BUSY are operational results. No per-event
allocation, repeated pointer validation, new kernel operation or native
completion callback is introduced.

## Cost ledger

IM0 changes **0 fixed, 0 root, 0 kernel, 0 idle and 0 per-public-Task reserved
bank-zero bytes**, including guards, alignment and unused capacity. The planned
additional frontend occupies an existing ordinary 1,600-byte or large
2,848-byte pool. That is capacity consumption, not new reservation. Input and
frontend stack requests remain provisional until emitted checks measure peaks.
The ABI slice will record its actual upper-RAM state and generated metadata;
no VRAM increase is needed for input.

Validation here is source/content/link review only. IM1–IM8 remain executable
work; current reference pages continue to describe the installed system.
