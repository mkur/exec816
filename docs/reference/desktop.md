# Desktop client service

[Reference](README.md) · [Layers](layers.md) · [Implementation plan](../plans/gem4xe/desktop-implementation-plan.md)

The DT1 native service implements window identities, retained command content
and asynchronous events. Hardware presentation and console attachment are not
yet connected. It is an ordinary library and message service above Exec; it
adds no kernel gateway or resident Task by itself.

## Registration and lifetime

`DESKTOP.Init(client, service)` creates a private reply port in the calling Task.
Client storage must be writable, address-stable and initially unbound. A failed
initialization leaves no published registration. `Prepare(request, operation)`
initializes a free request; `Submit(client, request)` publishes it and
`Collect(client)` returns a completed request or NULL. Use `EXEC.WaitPort` on
`client.replies` when no independent application work remains. Do not prepare
or resubmit a published request before collecting its reply.

Submit REGISTER before other operations. The presenter retains the owning Task
and the original client address. Keep the client, reply port, signal, requests
and borrowed payloads alive through collection. This is the Exec shared-memory
registration/lifetime contract, not a protection boundary. Admission audits
client storage; event and drawing requests do not scan writable-memory tables.
The caller must preserve the service allocation until all clients dispose.

There is one registration per Task and at most four registrations. Four request
lanes allow one control, one content replacement, one event wait and one event
cancellation concurrently. Each remains occupied until reply collection.
Request sequences and client/window IDs are 32-bit, never reused during the
binding/service lifetime; exhaustion rejects further allocation. Old window
IDs cannot address reused slots.

## Operations

Exact layouts, operation numbers and statuses come from
[abi/desktop.json](../../abi/desktop.json); regenerate with
`tools/generate_desktop.py`. Rebuild callers when these records change.

| Operation | Result |
| --- | --- |
| REGISTER | Retain owner and assign client identity. |
| OPEN | Copy a title of at most 31 bytes and create a hidden, fixed-size, fully onscreen window. Four slots include hidden windows. Return its ID in `window`. |
| SHOW / HIDE | Change visibility. Hiding the focused window clears focus. |
| MOVE | Set the top-left position from `bounds.left/top`; preserve dimensions. |
| RAISE | Move a window to the front. |
| FOCUS | Focus a shown window and retain focus-change notices. |
| REPLACE | Validate and copy one complete retained command batch, then invalidate its layer. |
| NEXT_EVENT | Reply with one available event, or retain the request without blocking other clients. |
| CANCEL_EVENT | Match `target` against the waiting request sequence; reply to it with CANCELLED before acknowledging cancellation. ALREADY_DONE means completion already won. |
| CLOSE | Remove the window and its queued events after active painting retires. |
| UNREGISTER | Require all windows closed and other lanes collected; publish the final reply and release service references under Forbid. |

A control reply acknowledges logical state, not scanout. During an active
Layers token, control/content requests wait in a bounded service queue while
event intake and cancellation continue. Each pump handles at most four
requests. A caller can mutate only its own windows.

REPLACE requires exactly one `Content` record: background pen 0–15, at most
32 fill/text commands and 256 text bytes. Coordinates are client-local and
half-open, within the outer rectangle minus 8-pixel side borders, 16-pixel title
area and 8-pixel bottom border. Text is 8 pixels per character and 8 pixels
high; offsets/counts must stay inside the supplied text. The entire batch is
validated before retained content changes. No payload pointer survives reply.
Console-kind records are reserved for the upcoming presenter integration;
DT1 does not attach or retain a console by storing its unit number.

## Events and shutdown

Each client has sixteen ordinary events. Adjacent motion coalesces only with
matching window, route and buttons. Overflow discards the ambiguous queue and
retains LOSS. Close-request and current-focus notices have separate durable
per-window bits. A stalled event consumer cannot grow storage or block another
client. The service's input producer supplies capture metadata; DT1's recording
backend does not acquire hardware input.

Cancel and collect NEXT_EVENT, collect other lanes, close every window, then
UNREGISTER and collect its reply before `Dispose`. Dispose deletes the private
port only when registration and all lanes are clear. Close requests from a
future gadget will be events, never forced Task removal. Removing a registered
Task is an Exec lifetime violation and produces the existing launch fault.

`DESKCORE.Init` uses a presenter-owned allocated signal; only that Task pumps,
changes the scene, or posts events. `Stop` succeeds only after clients, messages
and active painting retire. The embedding service owns signal/storage cleanup.
The DT1 fixture uses three Tasks solely to exercise these boundaries; the
production integration will reuse the console worker.

## Storage and validation

The generated service occupies 10,372 bytes in upper RAM, including the
4,782-byte Layers scene, four 444-byte client records, four 760-byte windows
and one 710-byte staging batch. Client records are 18 bytes and requests are
78 bytes, excluding their ordinary Exec reply ports. No new bank-zero pool,
stack or DP reservation is introduced.

[Development evidence](../history/desktop.md) records raw/optimized execution,
stack observations and limits. DT1 does not claim hardware presentation,
pointer latency, desktop readiness or whole-system qualification.
