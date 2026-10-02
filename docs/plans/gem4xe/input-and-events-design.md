# Input ownership and events for hosted GEM

[Implementation plan](input-and-events-implementation-plan.md) · [GEM work](README.md) ·
[Current VDI contract](../../reference/gem-vdi.md) · [Roadmap](../../roadmap.md)

Status: proposed design, following completed G0–G6. This note selects the
boundaries for an interactive graphics workload; it adds no supported API or
executable behavior. The companion implementation plan selects initial record
layouts, source changes and executable gates; its emitted ABI probes must pass
before runtime migration.

The next milestone is one application that accepts native keyboard input,
updates a small graphical dialog during physical disk I/O, and exits cleanly.
Reusable input capture belongs to Exec's platform layer. The application owns
interaction policy, and the existing renderer remains the sole graphics owner.
Use injected pointer events to establish cursor and button semantics before
adding a physical mouse backend.

## Existing behavior and constraints

The [hosted VDI subset](../../reference/gem-vdi.md) already provides drawing,
bounded hardware completion, one supervised client and exclusive display
ownership. G5/G6 demonstrate a computing Task and physical SDFS reads alongside
rendering. They do not provide input, AES or a desktop.

Keyboard capture currently belongs to the console. The native
[producer](../../../platform/altirraos/console.s) publishes raw key records with
capture-time route identities; [console input](../../../lib/console/consoleinput.act)
translates them in Task context. Separate route mailboxes preserve BREAK and
input loss even when the ring fills. Stopping the console releases keyboard
capture as well as presentation. Hiding its tiles does not release either.

The [existing assessment](exec816-integration-assessment.md#interrupts-and-input-need-shared-hardware-ownership)
identifies a second constraint: GEM's quadrature mouse sampler programs POKEY
timer and audio/serial registers also owned by
[native SIO](../../../platform/altirraos/sio.s). Importing the donor's input
startup or restoring its timer settings after disk calls cannot establish
concurrent mouse and SIO operation.

The current workload also treats a failed `D1:DATA.BIN` read as a fatal
assertion while graphics is owned. Mounting the standard demo disk can therefore
leave a partially drawn screen. The interactive launcher must unwind this
ordinary media error before returning to text.

## Scope and acceptance target

The first scene uses the existing 640×240 mode, sixteen pens and built-in font.
It contains a short text field, a color or counter control, a progress indicator
and an Exit button. Tab selects controls, Return activates the selection, and
Escape requests orderly exit. Printable keys and Backspace edit bounded text.
Keyboard navigation makes the artifact usable before physical mouse support.

Injected motion and button transitions exercise pointer selection, press and
release, and cursor restoration in development tests. The guide must identify
this as injected coverage; it does not advertise an emulator mouse as supported.
The first artifact uses a small application event loop and VDI primitives.
Importing AES object/form code is a separate follow-on slice with its own source
closure, pointer audit and stack measurements.

Acceptance requires visible input responses while a cold physical SDFS transfer
is active, exact disk contents, normal text restoration, and no retained input
producer or pending graphics packet after exit. Input loss must cancel a partial
gesture rather than create a click. A wrong or missing disk must produce a
readable error after safe graphics shutdown.

Multiple GUI clients, window management, menus, resource files, GEMDOS, G4A
loading, live console suspension and arbitrary application termination remain
outside this milestone. No general key rollover, key-release stream, mouse
wheel, double-click or drag behavior is implied by the initial keyboard path.

## Tasks and ownership

Use the existing eight-Task layout and both existing 2,560-byte stacks. Replace
the G5 computing peer with a C application Task. That Task starts the renderer
and becomes its sole client and service supervisor. The Action root performs
DOS I/O concurrently and coordinates overall startup and exit.

| Participant | Responsibility |
| --- | --- |
| Action root | Admit the application, perform bounded file reads, publish progress, request application stop and collect its retirement. |
| C application | Own input capture, normalize events, update controls, submit/collect drawing, and close/stop its renderer. |
| C renderer | Own the display lease, all VBXE access, scene pixels and cursor save/restore. |
| Existing filesystem and SIO workers | Execute disk requests through their current ownership and cancellation protocols. |
| Console worker | Own text presentation and input before graphics and after restoration; it is stopped during graphics. |

Admit the application and have it start the renderer before admitting small
workers that could consume either large pool. The application then waits for
the root's handoff acknowledgment before opening graphics or input. Record the
actual live Task inventory, including filesystem workers, in the implementation
evidence; a prepared descriptor is not an extra execution slot.

This preserves the service's single-owner rule. The root sends control messages
to the application; it does not submit through another Task's `GemClient` or
send a foreign STOP to the renderer. Retain the application, root notification
target and shared control storage until their final posts and replies retire.
No separate input worker, stack or DP is proposed.

## Reusable capture interface and console migration

Introduce an ordinary platform input library, provisionally `INPUT`, usable by
the console or another Task. Its conceptual operations are acquire, publish a
route, take captured records, acknowledge loss/cancellation and release. Exact
names, layouts and error numbers belong in a new machine-readable ABI during
implementation planning. Generate Action!, C and assembly definitions together.

One address-stable lease in upper RAM identifies the consumer Task, allocated
wake signal and a nonrepeating acquisition generation. Only one consumer owns
the keyboard source at a time. Acquisition returns BUSY when occupied; it never
steals ownership or waits for another owner to disappear. A copied lease or
stale generation grants no access. Acquisition prepares all retained state
before enabling capture; failure before publication leaves no partial owner.

The library retains captured records in a bounded queue. The owning Task drains
it after notification; signals only announce that work may exist. Translation,
focus, editing and cancellation policy remain outside IRQ code. This follows
Exec's producer/consumer and lifetime model, with driver policy outside the
kernel. An exclusive pull interface avoids another resident Task and the handler
chain of a general Amiga input device. It deliberately supplies neither global
event broadcast nor arbitrary interrupt callbacks.

The migration must replace the console's existing capture ownership, not add a
second independent keyboard implementation. Preserve console input bytes,
capture-time focus routing, foreground BREAK, per-route loss, clear behavior and
startup/stop rollback. Keep console-specific decoding and DOS foreground policy
in their current layers. Reuse the existing 64-record raw capture storage where
its layout permits, with one authoritative owner and generated placement.

The current [EXECPRODUCER](../../../lib/exec/execproducer.act) facility is serial
specific; it cannot already bind an arbitrary keyboard consumer. The console
uses private `$F3/$F4` admission operations in
[task-console.inc](../../../lib/console/task-console.inc). The proposed migration
replaces these with a reusable, source-qualified public producer binding for
the fixed platform serial and keyboard sources. Kernel policy validates Task
and signal lifetime; platform code retains source activation, masks and hardware
restoration. Do not add a GEM-only gateway or merely rename the private console
operations. Update serial and console callers together, rebuild them and remove
the obsolete interface. Keep `COP #$50`, preserve OS `$00`, and allocate no new
COP signature.

## Event identity and bounded delivery

Keep two identities distinct: the input acquisition generation and the
consumer's capture-time route tag. The latter preserves existing console focus
and foreground semantics. The GUI initially publishes one route for its entire
session; control focus is application state processed in event order. Old
records never become input for a newly acquired session. Generations refuse
admission before wrap and are not inferred from reused Task pointers.

Use the existing Exec tick for capture timestamps and unsigned elapsed-time
comparisons within half its range. Timestamps describe ordering and latency;
they are not session identities. Preserve FIFO order for events in the same tick.

| Event | Proposed meaning |
| --- | --- |
| KEY | A native key action with raw code, captured modifiers and a capture tick. Task-side decoding produces a character or navigation action. |
| POINTER | Absolute position within the fixed screen plus current buttons, from a declared backend. |
| BUTTON | An ordered button transition carrying the position and state at that transition. |
| LOSS | At least one record was lost or a backend could not preserve its state; invalidate any partial gesture or edit sequence. |
| CANCEL | Durable session cancellation, independent of ordinary queue capacity. BREAK and a captured Escape action request orderly exit. |

Keyboard hardware capture is not assumed to provide general key-up events or
continuous modifier state. Preserve modifiers reported with each action;
unsupported combinations produce no invented transitions. Do not add a timer
sampler or key-repeat scheduler as a hidden dependency. Normalization suppresses
only proven duplicate captures, preserving distinct later presses and the
console's current behavior.

Retain the current 64 raw keyboard slots. Budget a separate GUI queue of 32
normalized records, with a proposed maximum record size of 24 bytes. Freeze its
exact fields and alignment in the implementation plan. No allocation occurs
in an interrupt or per event. Drain a bounded batch on each application turn,
then check render completion and control messages so input cannot starve them.

Adjacent motion records may coalesce to the latest position only within the
same session and unchanged button state. Never coalesce across a button edge,
key action, loss or cancellation. Preserve button edges and their positions in
order; when capacity prevents that, latch loss and discard the incomplete
sequence. Recovery clears pressed/armed UI state and requires a fresh release
before another press can activate a control. A future physical backend must
resample authoritative state or remain unarmed until such a release is observed.

Loss and cancellation have durable state outside the ordinary FIFO. Preserve
console per-route BREAK mailboxes during migration. GUI cancellation is captured
even with a full raw ring and no pending read; it never kills a Task. Acknowledge
notification and durable state under one serialized protocol so a later event
cannot be erased. Pending cancellation prevents new interactive work but does
not skip completion collection or cleanup.

Configure a bounded raw-key cancellation filter before activating the source:
the GUI selects Escape/BREAK, while the console preserves Ctrl-C/BREAK routing.
The producer only matches admitted raw patterns and latches the captured route;
it does not run GUI callbacks or decide cleanup policy. Consuming cancellation
must not also activate a control through a duplicate ordinary key event.

Button handling arms one enabled control on press and activates it only on a
matching release over that control. A release elsewhere, loss, cancellation or
session retirement disarms it. Movement alone never activates a control.

## Interrupt publication and SIO coexistence

Preserve the [platform context protocol](../../reference/platform.md#vbi-preemption)
and complete S, D, registers and mode on asynchronous entry. Forbid serializes
Task-side ownership updates; it does not exclude hardware interrupts. Short
native IRQ-masked sections publish multiword route/binding state. NMI may still
tick and must defer switching according to the interrupted-I/SWITCHING rules.
Do not mask IRQ across queue walks, decoding, allocation or drawing.

Initialize a slot before publishing its producer index. The consumer copies a
complete record before releasing its slot. Route retirement disables new posts,
settles in-flight capture and queued wakes, then retires old tags and storage.
The producer's Task and signal cannot be released or reused until this finishes.
IRQs may use only admitted resident capture/binding storage, never traverse GUI
objects, DOS contexts or client message pointers. NMI does no input decoding and
neither interrupt path touches MEMAC or VRAM.

The migration must preserve SIO's serial-first dispatch, bounded keyboard work,
interleaved serial checks, IRQ-mask ownership and shared `SKCTL` restoration.
Test input-first and SIO-first acquisition and both release orders. Do not reset
keyboard scanning in the middle of a serial phase or restore a stale whole
POKEY register snapshot over a live owner.

Native keyboard tests use the matrix-input mechanism in the current
[graphics platform pin](../../../toolchain/altirra-gem-vdi.json). Injected pointer
tests enter through a checked test producer with the same event identity and
publication rules; they do not write GUI state directly. Keep injection out of
the distributed production binary.

Physical mouse admission is a later gate. Select one device, port, protocol,
sampling mechanism and exact emulator configuration. A frame-polled absolute
or counter device is a candidate, not established support. Audit PIA, POT and
POKEY ownership and measure lost motion, buttons, keyboard latency and serial
errors together. Quadrature support needs an explicit shared timing design or
another proven capture source; the donor timer installer remains excluded.

## Rendering and cursor serialization

The application waits on input, control and renderer reply signals. Submit at
most one drawing packet at a time and keep it immutable through exact reply
collection. While it is pending, continue draining input and coalesce dirty UI
state for the next packet. Calling a synchronous collect before processing input
would reintroduce stalls during long batches.

Bound interactive drawing to small updates; the 768-glyph G5 batch is a stress
workload, not the redraw unit for a key press. The initial performance target is
at most sixteen PAL ticks from native key capture to its first visible control
update during the selected physical-I/O workload, in raw and optimized builds.
This is a proposed acceptance target, not a measured guarantee. Record maximum
latency and workload limits; reduce batch work if it misses the target.

Add a private renderer request for cursor position and visibility, validated
through the generated service ABI. It does not imply full VDI cursor or raster
copy support. Use one fixed 16×16 masked cursor initially. The renderer saves
the covered background, draws the cursor and restores it before a move or any
scene update. After updating the scene it saves the new background and redraws
the cursor. Validate a complete request before changing even cursor pixels.

All save, restore and draw operations use the existing hardware fences and
mapping discipline. Cover clipping at every screen edge, odd pixel positions,
packed-pixel neighbors and drawing under a stationary cursor. The application
and interrupt handlers never map VRAM. Allocate explicit cursor scratch instead
of borrowing font/glyph storage that may still be in use. Close hides the cursor
before display release; unrecoverable blitter failure retains the existing
FAULTED/reset-required behavior.

## Handoff and orderly shutdown

The root closes text handles, releases its DOS context and waits for
`CONSOLEDRIVER.Stop()`. The application can then acquire presentation through
its renderer, acquire input, publish its route and announce readiness. Input
and display leases remain independent: holding one does not authorize the other.
Failure after either acquisition unwinds resources already acquired before
announcing failure to root. No live text endpoint is suspended or stolen.

During disk reads, root owns the file and its DOS context. Progress and exit
coordination use bounded, retained control messages; root must not wait for a
GUI response while the GUI waits for root to finish that same disk operation.
For the initial workload, a stop request prevents the next bounded read; the
current synchronous operation is allowed to complete within its existing driver
deadlines. Immediate cancellation of a foreign DOS operation is not promised.

On Escape, Exit, root stop, media error or recoverable renderer error:

1. Latch the first result and stop accepting new interaction or file work.
2. Retire input publication and its queued wakes; discard remaining session
   events without redirecting them to a later console session.
3. Collect any submitted renderer reply, then close the session, stop the
   renderer and dispose client storage. Only its application owner does this.
4. Root settles file I/O, closes an opened file and releases its DOS context.
   This may proceed alongside application cleanup, with an explicit completion
   acknowledgment before final application retirement.
5. Retire control messages, signals and Task leases, then restart the console
   after display ownership is FREE. Show completion or the original media error
   long enough to read, with a bounded hold, before final OS return.

If hardware cannot quiesce, follow the existing reset-required path and retain
the resources it can still access. A software timeout never authorizes freeing
an in-flight packet, signal target or DMA buffer. Startup and orderly teardown
must not require fresh allocations that failure has made unavailable: reserve
control/stop storage before readiness, and test exhaustion during exit.

Rename the distributed graphics companion disk to `gem-vdi/graphics.atr` and
update its guide, package whitelist and checksums together. The internal builder
may retain its existing staging filename. Preserve the cold first file access
after drawing starts; a disk preflight that warms caches must not replace the
physical-overlap check. Missing, short or corrupt workload files follow the
same cleanup path as a wrong disk.

## Memory budget

This documentation change reserves **0 fixed bank-zero bytes, 0 per public
Task and 0 for private idle**. The implementation target is also zero in each
category, including guards, alignment and unused capacity. The existing
[eight-Task budget](../../architecture/task-capacity.md#complete-bank-zero-budget)
reserves 56,128 bytes including OS ranges and leaves 9,408 bytes unreserved
after startup. No part of that free range is implicitly allocated by this note.

| Resource | Proposed placement and accounting |
| --- | --- |
| Application and renderer stacks | Existing two 2,560-byte pools, each with its existing interrupt reserve and external guards; no third large Task. |
| Raw capture and route records | Upper RAM; migrate the existing console capture allocation, counting any enlargement and alignment explicitly. |
| GUI event queue | Upper RAM; at most 32 × 24 = 768 payload bytes, plus separately measured queue state, loss/cancel state and alignment. |
| Leases, messages, bindings and UI state | Upper RAM; record full reserved/rounded extents and maximum simultaneous allocations in the build report. |
| C code and data | Start within the existing complete `$0C`/`$0D` banks; check linked capacity. Additional upper banks require an explicit map revision. |
| Cursor VRAM | Proposed 1,024-byte dedicated extent, including saved background, expanded mask and slack; final layout must prove disjointness. |

The [current VRAM map](../../../platform/altirraos/vbxe-vram.json) reserves
107,008 bytes. A new 1,024-byte cursor reservation would make 108,032 bytes,
leaving 416,256 of the private 524,288 bytes unassigned. It is separate from the
existing 4 KiB CPU aperture and any upper-RAM staging buffer. Update the map
only when implementing and validating the cursor allocation.

Measure raw/optimized stack peaks for the application, renderer, root, kernel,
idle and affected service workers. Existing G5/G6 peaks do not bound the new
event loop or cursor paths. Budget producer binding metadata and resident code
as well as event payloads; a zero bank-zero target is not a zero memory cost.

## Executable gates for the implementation plan

Use small development slices in this dependency order. These are design gates;
G0–G6 and their historical evidence remain complete and unchanged.

| Gate | Required result |
| --- | --- |
| Startup cleanup | Wrong/missing/short/corrupt disk reports an error after clean display restoration; no live ownership is lost. Distinct disk filename is packaged correctly. |
| Shared keyboard capture | Console uses the reusable producer and capture path; input bytes, focus, BREAK, overflow and stop/restart controls still pass. |
| Interactive keyboard scene | Application and renderer occupy the two large pools; native keys update controls during a real physical read; Escape settles outstanding work and exits. |
| Cursor and injected buttons | Exact pixels through move/hide/show, all edges and scene updates; ordered button behavior and explicit overflow recovery. |
| Physical pointer | One pinned backend passes hardware ownership, motion/button fidelity and SIO coexistence checks before being advertised. |
| Minimal AES | Separately select object drawing, one dialog and event waits after the input/cursor boundary is stable; no desktop implication. |

Focused emitted tests must cover raw Action! NIR/Calypsi `-O0` and optimized
NIR/`-O2`, generated layouts, all stack/domain guards and full context restoration.
Exercise capture/publication/release boundaries under IRQ/NMI, no-lost-wakeup
waits, stale acquisition and route tags, Task-slot reuse, signal reuse, generation
exhaustion, allocation failures, full queues and cancellation during drawing.
Use the existing console focus/BREAK cases as migration controls.

Observe input capture and changed pixels during an active physical transaction,
with exact file bytes and the pinned SIO profile. A queued request or pending
reply alone does not prove overlap. Compare cursor/background pixels against an
independent model and inspect actual scanout. Check final heap ownership, input
vectors/masks/shadows, unmapped aperture and OS display restoration. Repeat the
production artifact without test injection or substituted hardware status.

Future timer waits need a defined event/deadline mechanism. Current
[`Wait`](../../reference/signals.md#waiting-and-scheduling) has no timeout;
ordinary Sleep does not implement a wait for either input or a timer. Resolve
that contract in the AES plan, including wrap-safe deadlines and cancellation,
rather than claiming `evnt_multi` support from the keyboard loop.

Refresh any demo through [build_demo.py](../../../tools/build_demo.py), retaining
OF816, its five-second shell/prime autoboot, matching media, ROM and notices.
Run affected standard OF816 controls after the shared input migration. Package
only boot files, guide, notices and checksums; keep maps and evidence outside
the ZIP. Development results qualify only their recorded paths; release or
hardware qualification follows the separate [testing policy](../../contributing/testing.md).

## Design preparation checks

This note was checked against current platform, signal, console, display and
VDI contracts and the corresponding capture, producer, SIO and service sources.
The preparation checks content, local links, anchors and memory arithmetic.
It runs no new emitted-code test and makes no new executable compatibility claim.
