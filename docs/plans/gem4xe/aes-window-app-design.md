# AES window applications on Exec816

[GEM integration](README.md) · [Implementation plan](aes-window-app-implementation-plan.md) ·
[Hybrid model](hybrid-aes-vdi-design.md) · [Current AES contract](../../reference/aes.md)

Status: implemented through WA6, 2026-10-07. The
[execution record](../../history/aes-windows.md) tracks the slices; current
contracts describe the implemented interface. The foundation below records
the starting point for this design.

Build a small resident C counter application using ordinary GEM calls. It opens
a titled window, updates its contents on `MU_TIMER`, handles `WM_REDRAW`, and
responds to requests to top, move and close the window. Two instances must work
beside the native shell. This establishes the application redraw path needed
before menus, dialogs, resource files or a file-manager desktop.

Keep the [hybrid model](hybrid-aes-vdi-design.md): the presenter owns window
policy, callers own message/event waits and VDI drawing executes in the caller.
The application body should need only the supported GEM interface. Exec-specific
startup, endpoint attachment and Task retirement belong in its resident wrapper.
This is source compatibility for rebuilt applications, not GEM binary loading.

## Starting foundation and missing work

The current [AES layer](../../reference/aes.md) supplies registration, copied
application messages, message/timer waits and recursive update/mouse locks.
The native [desktop](../../reference/desktop.md) supplies frames, focus,
dragging, exposure and the [Layers scene](../../reference/layers.md).
The [hosted renderer](../../reference/gem-vdi.md) supplies the required text
and fill operations. The native Control Panel submits retained widget content;
it does not exercise a GEM application's window and redraw loop.

Three ownership changes are necessary: externally painted window contents,
durable GUI message delivery, and serialized display access from application
Tasks. Merely adding C wrappers around the current window and renderer helpers
would leave their presenter-only state and display lease unsafe.

Use the implemented mouse acceleration and tested PI3 usability as the starting
point. Broader latency optimization remains deferred; PI4 and HY4 stay open.

## First application profile

Support one created window and one virtual workstation per registered
application, with the existing four registrations and four desktop layer slots
shared with native windows. Creation reserves its slot even while closed.
Resource exhaustion is an ordinary reported failure. There is no new server Task.

| Interface | First supported behavior |
| --- | --- |
| Existing application/event calls | Preserve `appl_init`, `appl_exit`, `appl_write`, message/timer waits and `wind_update`. |
| `wind_create`, `wind_open`, `wind_close`, `wind_delete` | A fixed-size, on-screen `NAME \| CLOSER \| MOVER` window, with distinct created, open and deleted states. |
| `wind_set` | Set `WF_NAME`, top with `WF_TOP`, and move with `WF_CXYWH` while preserving width/height. |
| `wind_get` | Kind, current/work rectangles, top identity and `WF_FIRSTXYWH`/`WF_NEXTXYWH` visible work rectangles. |
| `wind_calc` | Convert work/border rectangles for the supported frame kind, using the same metrics as frame painting. |
| GUI messages | `WM_REDRAW`, `WM_TOPPED`, `WM_MOVED`, `WM_CLOSED`, with the pinned GEM eight-word layouts. |
| `graf_handle`, `v_opnvwk`, `v_clsvwk` | Obtain display metrics and open/close a private virtual workstation over the presenter's existing display. |
| VDI drawing | `v_bar`, `v_gtext`, `vs_clip`, fill/text colour, solid fill and replace-mode setters. Fixed 8×8 font and the existing sixteen-colour mode. |

Keep the donor spellings `WF_WXYWH`/`WF_CXYWH`; common
`WF_WORKXYWH`/`WF_CURRXYWH` aliases name the same fields. Freeze signatures,
message numbers, parameter counts and title-pointer word packing against the
[binding reference pin](../../../ports/gem4xe/aes-binding-inputs.json).
New wrappers and parameter-block entry points share one implementation.
Document unsupported fields, modes and opcodes as errors; do not advertise
a complete AES version or infer capabilities from the donor's larger API.

The initial profile excludes resizing, sliders, full-screen gadgets, menus,
resources, `form_do`, keyboard/button event extensions, arbitrary desktop
drawing, VDI raster copies, callbacks and forced termination. Window coordinates
are pixels; do not inherit the native console's character-grid positioning rule.
Off-screen and size-changing requests fail without changing geometry.

## Window authority and visible rectangles

Store an AES window record in upper memory, mapping an application-owned GEM
handle to a native desktop identity and Layers ID. The presenter alone changes
those records and the scene. Positive GEM handles do not repeat during the
service lifetime. Handle zero is the desktop work-area query, initially the
whole 640×240 display without a menu bar; it is not a writable application
window. `WF_TOP` reports zero when a native window is top.

Opening shows the layer and creates initial redraw work. Closing hides it but
preserves its handle and slot for reopening. Deleting retires the closed window.
`appl_exit` closes and deletes any remaining window. These semantics need an AES
adapter: native window close currently deletes the native identity.

Copy a bounded title at successful `WF_NAME` admission; use a 64-character
maximum plus terminator, rejecting longer titles without partial mutation.
The application may reuse its title buffer after return. This deliberately
differs from retaining a donor title pointer; changing the source buffer alone
does not update a title. Geometry and title validation happens at the window
operation, not again in each painting layer.

Preserve GEM's request/acknowledgment interaction:

- Clicking an inactive AES window sends `WM_TOPPED`; the application accepts
  with `wind_set(WF_TOP)`.
- A completed title drag sends proposed bounds in `WM_MOVED`; the application
  commits them with `wind_set(WF_CXYWH)`. The outline may move during the gesture,
  but committed geometry changes only on acceptance.
- The closer sends `WM_CLOSED`; the application decides when to close/delete.

Native windows retain their existing interaction. Deferred mouse controls obey
the existing update/mouse lock rules, and accelerated coordinates are consumed
as already transformed screen positions.

`BEG_UPDATE` freezes geometry and gives the application a published copy of its
visible work region. The service builds that copy; the application never walks
the shared Layers scene. Publish completed snapshots with a short state/pointer
transition rather than holding `Forbid` across region construction or copying.
`WF_FIRSTXYWH` resets a caller-local iterator and
`WF_NEXTXYWH` advances it, ending with zero width and height. Other simple
queries read coherent published records; mutations remain presenter RPC.
An owner mutation invalidates its previous enumeration and requires a new FIRST.
No Layers token remains held while the application executes or waits.

Convert GEM `(x,y,w,h)` and inclusive VDI corners to Layers' half-open bounds at
their respective boundaries, using widened arithmetic. Clip every draw to the
intersection of the window work area, its stable visible region, screen bounds
and the workstation's user clip. Clip-off removes only the user clip. This first
workstation profile is confined to its application's one window; broader GEM
screen drawing is future work.

## Durable redraw and control messages

The current sixteen-record `appl_write` pool must keep its capacity and FIFO
publication semantics. Add one separate, destination-owned GUI delivery record
per application, feeding the same receive port and `MU_MESAG` path. It carries
the ordinary eight GEM words plus private delivery-kind/window-lifetime metadata.
Ordinary application messages remain distinguishable without interpreting their
payload as trusted GUI metadata.

The presenter keeps bounded pending state per window: an invalid work-area
bound, close/top requests and the latest unreported move proposal. Duplicate
requests of one kind coalesce before publication; redraw unions may overestimate
damage. Retain first-pending order between kinds, including redraw, so repeated
motion cannot starve repaint. A published record is immutable. Later damage or
control requests remain pending until that record is consumed and recycled.
GUI messages and `appl_write` messages interleave in receive-port publication
order; they do not claim one global input-time order.

Recycling the GUI record atomically publishes its availability and wakes the
existing service signal when pending GUI work needs it. The service checks
pending state before sleeping. Use the existing short Task-side shared-state
protocol and endpoint publication holds; no polling, periodic AES wake, extra
timer or second application wait mechanism is needed. The dedicated record
ensures ordinary message-pool exhaustion cannot discard a close or redraw.

On close, discard pending work for that open lifetime; reopening has a new open
epoch and a full initial redraw. On delete/exit withdraw admission before
retirement. The receiver filters stale *service-originated* records against the
published lifetime before selecting a message result, then recycles them.
It must not discard ordinary `appl_write` payloads with similar words. Window
deletion never waits for its own Task to dequeue a message while blocked in the
delete RPC. Registration-owned delivery storage survives until the existing
exit drain and publication holds are complete.

## Application painting and damage handoff

Add an externally painted desktop window kind. The presenter paints its frame;
the application owns its work-area pixels and reconstructs them from its model.
Moving, opening, topping and exposure generate redraw obligations in addition
to any frame/background repair.

Do not treat sending `WM_REDRAW` as successful application painting. Add an
explicit external-paint damage handoff to Layers/desktop: while the presenter
has a stable damage snapshot, it completes its visible frame work and transfers
the work-area damage into durable pending GUI state. Only that completed
handoff may retire the corresponding manager damage. This needs a distinct
completion path; the present `Finish(success)` contract means pixels were
painted and fenced. Release the scene transaction before awaiting an app.

Once a redraw message is consumed, completing that repaint is the application's
responsibility, as in a normal GEM event loop. New invalidation creates another
obligation and cannot be erased by recycling the older notification. A hidden
window does not repeatedly wake its owner; new exposure supplies the redraw.

Application content remains ineligible for clean-source move/copy optimizations
and VRAM snapshots throughout this milestone, including after notification
delivery. There is no inferred pixel-validity acknowledgment or private
`redraw_done` call. Moving an application window invalidates and repaints it;
native retained-window optimizations remain available. This avoids extending
GEM's application API just to support caches before the redraw path is proven.

## Private workstations and shared display access

`v_opnvwk` creates caller-local parameter arrays, attributes, clip state and a
virtual handle. It returns an honest 57-word workstation description for the
supported subset. It must not call the physical display-open routine, clear
the desktop, change its palette or acquire a second DISPLAY lease.
`v_clsvwk` retires only the virtual state. Attribute setters and `wind_calc`
run locally. Retain normal operational errors through diagnostics for classic
void-return VDI calls.

The existing [DISPLAY lease](../../reference/display.md) is tied to the
presenter's Task. Introduce explicit, reusable delegated access in that library
and the drawing adapter. The presenter retains lifetime ownership; each attached
application has an address-stable upper-memory access grant established at
admission and revoked during orderly retirement. Do not pass the presenter's
lease pointer as if another Task owned it.

A short physical access transaction serializes all renderer scratch, selected
workstation state, CPU staging, MEMAC mapping, command arena and cursor saved
background. Every native and application rendering entry uses that arbiter.
Choose queued Task-side admission with ordinary Exec signals; publication and
sleep use a lost-wakeup-safe state transition. A waiting borrower gets a turn
after the current bounded unit; continuous native output cannot starve it.
The presenter uses nonblocking admission and keeps servicing messages and
input when a borrower owns access.

The application holds `BEG_UPDATE` around its ordinary visible-rectangle redraw
loop. That logical lock stabilizes layout and excludes native content painting;
it does not itself grant hardware access. For each bounded drawing unit:

1. Admit physical access after previous native DMA has been completed and
   retired by its presenter owner. Select the caller's private attributes and
   the frozen visible/user clips.
2. Remove intersecting cursor/overlay pixels through the shared renderer,
   execute the trusted bounded drawing unit, and fence it synchronously.
3. Restore the cursor consistently, release physical access and wake eligible
   waiters before another unit can begin.

Start with synchronous, fenced application drawing so its completion never
depends on the presenter processing a GUI request while blocked by that drawing.
Keep existing asynchronous native DMA retirement in its owner. Release physical
access between renderer chunks, including long text chunks; keep attributes
and clip state caller-local across those boundaries. Existing list/work limits
bound chunks, and their actual CPU and cursor costs must be measured. A complete
work-area repaint must not become one hardware-ownership unit.

The lock order is logical update ownership, stable clip snapshot, then physical
access. Never issue AES RPC, wait for an event, invoke application callbacks or
release update ownership while holding physical access. A synchronous bounded
device fence is the only hardware wait inside it. No rendering happens under
long `Forbid` or interrupt masking; IRQ capture and VBI preemption continue.

Resource admission establishes trusted identities and supported attributes.
Hot internal clipping/building does not repeat pointer, geometry and list
validation at every layer. Preserve capacity, fault and ownership transitions.
If hardware faults, revoke admission and use coordinated driver recovery: only
the lifetime owner may finish display teardown once borrowers are quiescent.
An unquiesced fault retains ownership/storage and the current reset-required
behavior. Cooperative exit cannot revoke a running Task's live hardware access.

## Application lifecycle

The resident wrapper attaches to AES, runs the GEM application, detaches, then
permits ordinary Exec Task retirement. The application initializes AES, gets
display metrics, opens its workstation, creates/titles/opens its window and
enters `evnt_multi(MU_MESAG | MU_TIMER)` with a one-second interval. Both ready
bits are handled when returned together. This is a periodic UI demonstration,
not a precision elapsed-time clock; unrelated messages can restart its wait.

On redraw, take `BEG_UPDATE`, query the work area and enumerate visible
rectangles. Intersect each with the redraw bound, set `vs_clip`, clear the
intersection and draw the counter model. Release the update lock before
returning to the event wait. Timer updates use the same redraw helper with the
changed text area; they never draw through an occluding window. Close/top/move
messages use the ordinary calls described above. Cleanup closes/deletes the
window, closes the workstation and exits AES, unwinding partial startup too.

## Capacity and acceptance

Target additional reserved bank zero of **0 fixed + 0 per public Task + 0 idle
bytes**, including guards, alignment and spare stack capacity. Add records,
parameter arrays, copied visible regions and access grants in upper memory;
reuse renderer tables and staging rather than reserving a staging page per app.
Measure and report live/reserved upper bytes and linked banks in each slice.

The [eight-Task and stack pools](../../architecture/task-capacity.md) are real
constraints. Drawing depth must be measured on the application's stack; the
existing message-only C clients do not prove it fits. Use existing stack classes
and include both peak interrupt reserve and bridge/renderer depth. A demo can
replace the native panel with the counter, with a separate two-instance case;
do not simply add clients to an already full disk/pipeline scenario. Any required
pool enlargement needs a revised, explicit bank-zero budget before proceeding.

Acceptance requires two independent application windows, correct overlap repair,
native shell/disk coexistence, durable GUI delivery under deliberate backpressure,
bounded access handoff, stack/context safety and complete cooperative teardown.
Record repaint and input p50/p95/max against matched existing workloads, without
turning this feature milestone into a new latency-tuning campaign. Existing
PI4/HY4 failures and the recorded pre-existing caret artifacts remain explicit;
no new application pixel mismatch is acceptable. The implementation plan turns
these requirements into individually executable commits.
