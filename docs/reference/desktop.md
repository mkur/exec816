# Desktop client service

[Reference](README.md) · [Layers](layers.md) · [Implementation plan](../plans/gem4xe/desktop-implementation-plan.md)

The native service implements window identities, retained command content,
asynchronous events and a worker-hosted bitmap presenter. DT4 connects one
64×20 shell console and retained graphical windows to Layers. It is an ordinary library and message service above Exec; it
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
| SET_TREE / UPDATE_WIDGETS / READ_WIDGET_STATE | Retain, patch or read [AES widget content](widgets.md) through the content lane. |
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
Console-kind admission is limited to the root controller and permanent console
unit 0, with a 528×184 outer rectangle and an 8-pixel placement grid. It cannot
attach an arbitrary console unit. The presenter owns the permanent model; its
shutdown refuses live desktop registrations. The root owns the shell streams
and closes them before retiring its window.

## Events and shutdown

Each client has sixteen ordinary events. Adjacent motion coalesces only with
matching window, route and buttons. Overflow discards the ambiguous queue and
retains LOSS. Close-request and current-focus notices have separate durable
per-window bits. A stalled event consumer cannot grow storage or block another
client. The service's input producer supplies capture metadata. DT2 still uses the
console's keyboard consumer; graphical keyboard routing and physical pointer
integration are DT3. Programmatic focus currently affects presentation.

Cancel and collect NEXT_EVENT, collect other lanes, close every window, then
UNREGISTER and collect its reply before `Dispose`. Dispose deletes the private
port only when registration and all lanes are clear. Close requests from a
future gadget will be events, never forced Task removal. Removing a registered
Task is an Exec lifetime violation and produces the existing launch fault.

`DESKCORE.Init` uses a presenter-owned allocated signal; only that Task pumps,
changes the scene, or posts events. `Stop` succeeds only after clients, messages
and active painting retire. The embedding service owns signal/storage cleanup.
The DT1 fixture uses three Tasks solely to exercise these boundaries. The
production presenter reuses the console worker and its existing 2,560-byte
stack; its message port adds one owned signal, not a new Task.

Native and AES admissions share a four-request turn budget. Each admission,
including a native request deferred by scene ownership, gives captured input
an opportunity before the next request. Completed cache/move transactions and
released console borrows also have input boundaries. These service capture and
the quiescent pointer without yielding or changing model-commit ordering;
widget gestures still wait for the existing scene and AES gates.


## Presentation

Select desktop mode before starting the console. The root launch adapter binds
an upper-RAM service, then registers and shows the permanent console as a framed
shell. The existing full-screen bitmap and standard text startup modes remain
available. Desktop mode rejects the console's tiled Create/Show/Hide/Focus
operations; use window controls for desktop placement and visual focus.

The same worker owns console I/O, the display lease and every physical draw.
Background, frame and retained content repair use Layers' visible damage. One
update token spans a repaint continuation of at most sixteen scanlines or four
retained commands per turn; console model writes and layout edits wait while
input delivery and request intake continue. No application refresh callback
runs inside the presenter. Covered damage is retained without keeping the
worker runnable; later exposure reconstructs pixels from the current model.

Ordinary console spans keep the existing short-write presentation pass. Each
synchronous public draw holds a token through all clipped fragments. The
native/C bridge supports half-open pixel clips, including odd nibble edges and
partial glyphs. Fully visible text retains the font-atlas path. Repainting does
not acknowledge edits that occur after its token: model edits are gated until
that token retires.

A scroll can reuse pixels only when the layer is clean and fully visible.
Its existing copy/fill list holds the scene token until completion IRQ/watchdog
processing proves completion or quiescence. Obscured scrolls update retained
cells and redraw visible damage. Before consuming more output, an obscured
visible console drains its existing row damage using the ordinary bounded
presentation passes. This prevents repeated scrolls from restarting repair at
the top and starving the lower rows. Input, cancellation and desktop controls
continue between passes. This redraw path remains slower than an unobscured
hardware copy; it does not reuse partially visible scroll sources.
Long writes use the existing batch limits (four rows, 256 bytes, four worker
turns or a tick boundary) before repainting the resulting model once. A batch
admitted behind another window keeps its redraw path even if exposure changes
before publication; newly repainted pixels cannot become a scroll-copy source.
No per-frame polling is added. Existing
reset-required hardware faults cannot return to free referenced storage.

The presenter acquires the ST mouse source on joystick port 1 with the existing
Timer 1 sampler and left button. A separate owned signal and route wake bounded
input draining; idle turns do not call Take just to discover an empty queue.
Desktop movement uses a fixed **two screen pixels per decoded ST step**, with
no acceleration. The presenter acquires bounded controller coordinates, then
scales them once before pointer drawing, hit testing, events and dragging.
Coordinates are absolute and clipped to 640×240. Interior coordinates move in
two-pixel increments; the inclusive right/bottom edges remain reachable at
639/239. Overshoot is discarded in controller coordinates, so reversing at an
edge moves immediately. `POINTER_PIXELS_PER_STEP` in `abi/desktop.json` records
this desktop policy. Hardware capture and the general input API remain
independent of screen geometry and sensitivity.

Each graphical window has a keyboard route. Focus commits that route together
with the console foreground selection. Captured keys and BREAK keep their route
through later focus changes. Graphical KEY events contain the raw Atari scan code
and qualifiers, not translated ASCII; CANCEL represents BREAK or the configured
cancel key. Console routes retain their existing translation and Process-group
cancellation policy. Event flags preserve INPUT.TICK_VALID; durable notices do
not invent capture timestamps. Delivery sequence numbers are monotonic.

Pointer hit testing and click-to-focus run in the presenter. Focus changes wait
for a live drawing token to retire. The pointer restores its saved background
before intersecting drawing and is shown after each quiescent quantum, including
an early pass after input intake. Motion accumulates during DMA; input delivery
continues. Both odd/even mask variants stay in VRAM, avoiding per-move mask
uploads. A visible move submits restore/save/AND/OR as one synchronous list;
show uses three records, hide one, and an unchanged valid pointer launches none.
The command arena remains exclusive to a pending asynchronous scroll. Cursor
batching adds no asynchronous request or completion signal. Capture runs at
about 4 kHz, with the [shared timer's SIO exceptions](input.md#st-mouse-capture).
A source loss disarms interaction until a released-button observation. Closing a
graphical window discards and retires its route; shutdown releases the source,
signal and software pointer before the display and keyboard retire.

Dragging a title captures subsequent motion and release outside the original
window. An XOR outline follows the latest position without a nested input loop.
Release commits onscreen, eight-pixel-aligned geometry after active painting or
DMA retires. Layers then repairs old and new exposed pixels from retained content.
Escape, source/event-queue loss, hiding, retirement or an external move cancels
the gesture. A released-button observation is required before another gesture.

The outline is below the pointer and removed before intersecting drawing. Four
blitter records toggle its disjoint edges; it adds no VRAM backing bitmap.
Graphical close gadgets publish durable CLOSE events. They do not force a Task
to retire, and an application may decline. The shell has no active close gadget;
its normal EXIT path controls retirement.

Pointer and move-repair response targets have not all passed. The execution
record separates exact capture/pixel correctness from measured responsiveness.
The [mouse performance record](../history/mouse-performance.md) compares the
4 kHz sampler and batched pointer with the earlier desktop.

## Shutdown admission

The root startup controller calls `DESKBOOT.StopAdmission()` before requesting
application retirement. The service's live byte advances from accepting (1) to
draining (2), then stopped (0); it does not reopen. Only that controller may
close admission. `DESKTOP.Init` then refuses new bindings, and dispatch replies
CANCELLED to queued/new Register or Open requests. Existing clients may still
replace content, receive/cancel events, close and unregister while they drain.
The controller retains the service until all clients, replies, paint tokens and
hardware references retire. No IRQ reads this admission flag or follows clients.
Partial shell admission unwinds its window, registration and port in reverse
order. An unquiesced blitter fault retains referenced storage until reset.

## Demonstration client

Build the optional local preview with `tools/build_demo.py --desktop`; the
[distribution guide](../desktop-distribution.txt) describes ST/port 1 setup,
interaction and the outstanding timing limits.

`DESKAPP` owns an ordinary 1,024-byte-stack Task and one 176×120 widget client.
Its compiled-in Control Panel has a toggle, two sibling radio buttons, Apply
(default/momentary), Cancel, a disabled button and a status label. It consumes
semantic widget events, reads authoritative state, and patches only the label.
Revision conflicts retry between turns with Stop checked; LOSS reads current
state without synthesizing an action. It initially leaves focus on the shell. A CLOSE event leads
to cooperative retirement; shell EXIT asks it to stop and waits for reply/storage
retirement. No application callback runs inside the presenter.

## Storage and validation

The generated service occupies 12,342 bytes in upper RAM, including the
5,074-byte Layers scene, four 668-byte client records, four 780-byte windows,
one 710-byte staging batch, sixteen deferred widget input records and two
fourteen-byte snapshot records. Public
client handles are 18 bytes and requests are
92 bytes, excluding their ordinary Exec reply ports. The service heap request
rounds to 12,344 bytes at Exec’s eight-byte alignment; unused window/queue/list
capacity is included. DT3 runtime/controller globals have 280 payload bytes in
upper image RAM (plus compiler alignment). Pointer save/masks reserve 1,280 VRAM bytes at `$37000–$374FF`, an increase of
256 reserved bytes (the former slack is now used). The command arena starts at
`$38000`; there is no overlap or additional CPU aperture. No new bank-zero pool,
stack or DP reservation is introduced.

[Desktop development evidence](../history/desktop.md) and the
[rendering record](../history/desktop-rendering.md#dr7-combined-measurements-and-local-preview)
record execution, stack observations and open timing limits. DR0–DR7 add no
reserved bank-zero bytes; snapshot VRAM grows by 131,072 bytes. These checks do
not establish physical-device or whole-system qualification.

## Copied moves

Programmatic MOVE and drag release share one presenter continuation. A clean,
fully visible front window with even X/width can copy its complete rectangle
through the IRQ-completed typed driver operation. Dirty, covered and unaligned
sources use retained redraw. The scene token gates model/layout changes and
queued HIDE/CLOSE while the copy is active; input capture can continue.

The reply acknowledges committed geometry after successful DMA, before all
exposure repair or final scanout. A quiescent transfer fault returns DRAW_FAILED
and retains the old geometry with touched pixels invalidated. An unquiesced
fault keeps the existing reset-required retention behavior. Console moves
preserve circular cells, dirtiness and presentation generation, updating only
placement and caret bookkeeping; ordinary focus changes still invalidate.

### Private client snapshots

The VRAM map reserves two 64 KiB compact snapshot slots at `$50000` and `$60000`.
`DESKCACHE` stores client pixels only; frames and console content remain retained
drawing. Even-width images must fit one slot and the 640 by 240 copy limit.
Window identity, visual revision and dimensions determine validity; position is
not part of the local image. Exhausted revisions disable caching. A pinned slot
cannot be evicted or reused before DMA retirement. Invalid slots are selected
first, then the least recently used unpinned slot. The generated Service is
12,342 bytes, including the two fourteen-byte slot records and alignment.

Capture holds a Layers read token, strips overlays, and becomes valid only after
matching completion. Restore borrows the caller's paint token until completion.
Quiescent failures retire the pin and follow display recovery; an unquiesced
fault retains all referenced storage. Closing a window invalidates its snapshot
identity before clearing the record. There is no public offscreen drawing API.

Capture runs only after input, controls, model writes and visible damage have no
work pending. Each eligible visual revision gets at most one attempt; eviction
does not cause a recapture loop. The console is uncached. Accepted content/tree
updates (including hidden updates), widget interaction and client focus styling
invalidate revisions. Frame-only command-window focus changes damage the title
and preserve the client snapshot. Position alone preserves local cached pixels.
Font and palette are fixed for the display lifetime; changing them while windows
are live is unsupported and any future setter must invalidate client revisions.

Painting always redraws the frame. A valid even-aligned visible client fragment
restores asynchronously while retaining its paint token and source pin; only
completion advances the strip. Unaligned fragments use retained drawing without
expanding over an occluder. The sixteen-scanline/four-command preparation limits
remain. A fully visible nonconsole client cannot contain the console's clipped
caret; the bridge removes intersecting pointer/outline overlays at capture.
