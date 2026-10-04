# Desktop implementation plan

[Design note](desktop-design.md) · [Plans](../README.md) ·
[Roadmap](../../roadmap.md)

Proposed, 2026-10-04. Implement the first Exec816 desktop by evolving the bitmap
console worker into one presentation service. Deliver a framed movable shell,
the existing ST mouse, and a second independent application with an overlapping
window. Establish the window ownership and event contract that can later host
selected GEM AES code. Commit each completed executable slice separately.

Layers is implemented; desktop presentation is not. This plan does not claim
that its timing targets or combined stack budget have passed. Current
[console](../../reference/console.md), [input](../../reference/input.md),
[Layers](../../reference/layers.md) and [display](../../reference/display.md)
contracts remain authoritative until the corresponding slice updates them.

## Scope and architecture

Keep the pinned 640×240 VBXE mode, GEM 8×8 font, circular console cells, batched
output and blitter completion IRQ. Use fixed-size, fully onscreen windows,
initially aligned to the character grid. The first shell is 64×20 cells plus
its frame. Desktop selection happens before service startup; changing a live
text console into a desktop is outside this milestone.

The presenter owns the display lease, drawing state, scene, pointer, caret and
drag outline. Console I/O, window interaction, Layers and drawing remain separate
modules within that Task. Use ordinary internal calls between them. Application
requests cross an Exec message port at window or content-batch boundaries;
individual glyphs do not require messages. Keep console short-write presentation
in the same worker turn where its current contract permits it.

This follows the Amiga separation between Exec mechanisms, Layers geometry and
Intuition interaction. One serialized presenter is the deliberate adaptation
for the 65816 stack budget and non-reentrant drawing state. Window policy and
driver queue policy stay outside the kernel. No desktop-specific gateway,
sampling Task, Task per window or second renderer is introduced.

Start with four ordinary layers plus the background. A frame and its client
area share a layer; hidden windows still occupy slots. The pointer, caret and
outline are coordinated overlays, not extra window layers. Expansion to eight
requires a separate rectangle-capacity proof, storage accounting and overlap
measurements. It is not needed to demonstrate two independent clients. Console
instance capacity and Task capacity are separate limits.

Defer resizing/reflow, partly offscreen windows, backing bitmaps, file browsing,
menus, arbitrary application callbacks, full AES bindings and G4A loading.
Adapt useful GEM frame/pointer/drawing code with its notices; do not bring its
cooperative scheduler, nested modal loops or standalone hardware ownership into
Exec. Action! client bindings suffice initially; existing internal C drawing
bridges remain part of emitted-code validation.

## Window and client contract

Define generated records in a proposed `abi/desktop.json`, with ordinary-call
client bindings and a service implemented above Exec. DT1 fixes exact layouts,
limits and status values before its emitted fixture runs. Rebuild all callers
together when these layouts change; do not retain compatibility variants.

Use the existing [message and port rules](../../reference/ports.md). Registration
retains an address-stable client record and its owning Task. The client keeps
its completion port and signal alive until unregister and reply collection
finish; Task retention alone does not retain arbitrary port storage.
Admission establishes valid storage and authority; ordinary calls trust that
live registration while still checking dynamic identities, bounds and state.
Do not add writable-memory table scans per input event or drawing primitive.
This is a shared-address-space lifetime contract, not memory protection.

| Operation | Proposed semantics |
| --- | --- |
| Register | Admit one client per owning Task and return a non-reused client identity. Allocate bounded upper-RAM state before publication; unwind partial admission. |
| Open | Create a window with a copied title, fixed bounds and a content binding. Return a non-reused window identity distinct from its layer and console unit. Reject capacity exhaustion without changing the scene. |
| Show, Hide, Move, Raise, Focus | Queue a bounded control request. Apply at a safe presentation boundary; reply after logical state commits. This reply alone does not promise final scanout. |
| ReplaceContent | For a simple graphical client, validate and copy a bounded retained batch of fill/text commands. Atomically install it and invalidate content; reply once borrowed input is no longer needed. |
| NextEvent | Allow one outstanding request per client. Reply with one queued event, or retain the request until an event arrives. The presenter continues serving other clients. |
| CancelEvent | Cancel an outstanding NextEvent by request sequence. Event completion and cancellation have a defined winner; the original request is replied exactly once. |
| Close | Retire the window after its active drawing and references settle. Distinct from the user requesting that an application close. |
| Unregister | After windows close and other replies are collected, withdraw the client, settle any event wait and acknowledge release of service references. Only then may client storage and ports retire. |

Bound each client to one content request, one ordinary control request and one
event wait outstanding. Permit event cancellation/retirement through a separate
bounded control record so waiting for input cannot prevent shutdown. Separate
request sequence and window identities reject stale completions. The client
never reuses a published message or borrowed payload before collecting its
reply; the service never touches a request after publishing its reply.

Propose sixteen queued events per client. Include window identity, capture or
service sequence, coordinates, buttons and relevant route generation. Deliver
keys to either CON input or the graphical client's event stream, never both.
Keyboard and BREAK retain their capture-time destination through focus changes.
The presenter consumes the pointer source and resolves window hit testing and
gesture capture in Task context; no IRQ follows window or application pointers.

Coalesce adjacent motion only where it preserves route, button and gesture
ordering. Preserve button transitions; queue exhaustion records durable LOSS
and cancels the incomplete gesture. A pending close request and current focus
state have durable per-window bookkeeping, so a full ordinary event queue cannot
silently erase them. A client that stops collecting events cannot stall other
clients or grow memory without bound. Require a released-button observation
after loss before arming another gesture.

The graphical test client uses a retained list capped initially at 32 fill/text
commands and 256 text bytes per window. Stage a complete replacement in upper
RAM and install it only after an active paint retires. Paint the content
background and replay the latest list through visible damage; this also removes
imagery omitted by a replacement. Validate the whole batch before publishing it.
The presenter does not call application code to refresh a window and does not
perform application file I/O. General immediate-mode drawing is later work.

The shell remains a DOS/CON client. Its launch/controller adapter creates the
64×20 console instance, connects inherited streams, registers the window and
retains the console/Process lifetime. Record the actual owner explicitly rather
than treating a window ID as a Process. The existing shell EXIT path initiates
cleanup. Leave a shell close gadget inactive until an explicit cooperative exit
protocol exists. A graphical close gadget sends CLOSE_REQUEST; it never removes
a Task forcibly. Client refusal or a delayed response leaves the window live.

## Presentation and completion

DT2 must separate content coordinates from desktop placement in the existing
[console display](../../../lib/console/consoledisplay.act) and
[bitmap bridge](../../../lib/console/console-bitmap.c). Translate client-local
coordinates once and intersect them with the frame/client bounds and Layers'
visible rectangles. Define clipping for partial glyphs, including cuts inside
an 8×8 cell; rejecting or rounding away a valid clip is not acceptable. Respect
VBXE pixel alignment without writing outside the permitted rectangle.

Layers damage drives exposure repair; console dirty spans still bound content
updates. Acknowledging one paint must not erase later edits. A fully hidden
window retains its content without drawing. Moving or uncovering it reconstructs
the exposed area from its current model.

Hold a Layers update token until the corresponding drawing has completed or is
proved quiescent. Keep one hardware list in flight. Input capture, input delivery
and bounded request intake continue while drawing and dependent model/layout
edits wait. Resume through the existing completion IRQ and watchdog; do not
introduce one-poll-per-frame completion or a busy-yield loop.

Allow the existing asynchronous scroll copy/fill only for a clean, fully visible
layer with valid source pixels and no intersecting overlay. Otherwise update
retained content and redraw visible damage. The current general rectangle copy
is synchronous; initial move commits may repaint. A general asynchronous move
requires its own reusable driver extension and evidence if later justified.

Remove intersecting overlays before modifying underlying pixels. Restore only
against the completed presentation, in a defined outline/caret/pointer order.
Pointer motion can accumulate to a latest position during DMA, but button edges
and gesture boundaries cannot disappear with it. An unquiesced hardware fault
retains the token and referenced storage under the existing reset-required
contract; a timeout must not free memory still reachable by hardware.

Service completion and input before another bounded rendering quantum. Rotate
runnable clients so bulk shell output cannot monopolize the presenter. Return
to input/control processing between clipping regions or bounded command chunks.
Wait only when no actionable work remains, following the current durable-wakeup
protocol. Do not wait inside the presenter for a client event reply, a mouse
release, an application redraw callback or an application-owned lock.

## ST mouse checkpoint

Keep the existing ST mouse on joystick port 1 and left button. Initial desktop
integration reuses Timer 1 capture, shared SIO timing, native/ROM IRQ paths,
decoding, loss notices and the registration/lifetime contract unchanged.
Sampling stays independent of presenter turns, repaint frequency and window
count. Do not move phase decoding into a per-frame GUI poll or change timer
programming merely because window drawing is slower.

Run the focused checkpoint in DT3, after the single window and pointer work and
before DT4 dragging. Bring it forward if ordinary movement loses distance,
reverses incorrectly or misses button edges. Use separate measurements to decide
whether any fix belongs in sampling, queue service or rendering.

| Stage | Record and check |
| --- | --- |
| Controller to capture | Independent electrical phase/button trace, actual sample intervals and maximum gap, decoder counts/directions, IRQ elapsed time and aggregate CPU share. |
| Capture to consumption | Event queue residence, wake/dispatch delay, coalescing, queue occupancy, durable loss and preserved button boundaries. |
| Consumption to visible pointer | Removal/draw CPU, waits for in-flight work, submission/completion and final scanout; blitter completion alone is not visible response. |

The [M5 record](../../history/gem-mouse.md#m5-coexistence-and-failure-closure)
measured a 275.946 µs maximum sample gap and seven PAL ticks of visible cursor
delay in its selected older workload. Those are historical observations, not
current desktop results. The supported stimulus has at least 1 ms between
per-axis phases and button levels held at least 10 ms. On the pinned controller,
the fastest qualifying phase interval was 16 scanlines, about 972 transitions
per second per axis; do not call that an exactly 1 kHz generated test.

Preserve the strictly less than 1 ms maximum sampling-gap gate and compare
captured counts against the independent trace. Also exercise faster bursts as
negative controls: three/four hidden quadrature transitions can look legal or
unchanged, so zero LOSS reports alone cannot prove zero missed movement. Report
the boundary without claiming support for arbitrary host bursts.

Exercise idle motion, sustained diagonal motion, reversal, held buttons, motion
at screen edges, shell scrolling and a cold physical disk read. Add a focused
FASTEST125 coexistence case because sampling and SIO share the timer. Loss and
queue pressure must cancel gestures without producing a synthetic click.
Route changes, source reacquisition and holding the button during shutdown must
not rearm a stale gesture. Recheck the relevant sample-gap and SIO cases if DT3
changes IRQ code or timer policy; document any changed envelope explicitly.

The current protocol has no acceleration. Sensitivity/acceleration is a later
Task-context policy decision; it must not hide missing electrical transitions.
Amiga mouse support, right-button support and hardware qualification are separate
work. Additions to the pointer protocol require their own admission and tests.

## Executable slices

### DT0 Freeze inputs and integration budgets

Record the current compiler, ROM, actual mouse-capable emulator, display mode,
memory profile and baseline shell artifact. Reuse existing console and mouse
measurement records where their inputs and workload match; do not repeat their
full matrices. Freeze the unchanged image for missing comparable measurements;
DT3 runs its new scanout observer against that image and the desktop. Existing
drawing-return timings must not be relabelled as visible-response measurements.

Inventory live Tasks at boot, shell prompt, external command, two-command
pipeline and shutdown. Reserve the existing large presenter pool before smaller
clients can consume it. Map upper-RAM scene/client storage, bounded content and
event buffers, the existing aperture and all VRAM users. Select the shell/window
controller owner and stream cleanup ordering. Record proposed module boundaries
and generated ABI inputs without introducing a second console implementation.

Acceptance: a reproducible unchanged shell smoke run, compatible baseline links,
Task/stack/memory ledger and explicit resource rejection paths. This slice adds
only evidence/harness scaffolding, not a new renderer or runtime reservation.

### DT1 Register clients and exchange window events

Implement the generated native records, client bindings and presenter-side
request dispatcher using a recording backend. Exercise Register/Open/control,
NextEvent/cancel, Close and Unregister with two independent Tasks. Implement
bounded queues, non-reused identities, exactly-once replies, owner retention,
admission rollback and slow-client handling before attaching hardware.

Acceptance: raw/optimized emitted fixtures prove one waiting client does not
block another; event/cancel races, queue loss, stale handles, full capacity and
retirement while requests are queued complete without leaks or unsafe reuse.
The ordinary console still runs through its existing backend. Publish the
implemented subset in a new desktop reference page and index it. Apply the
repository licence map to new public bindings and preserve donor notices.

### DT2 Present one framed shell through Layers

Connect the existing worker, retained console model, scene and drawing bridge.
Show a desktop background and fixed framed shell. Route all physical drawing
through the presenter, integrate clipped text/fills, scrolling admission,
completion tokens and retained damage. Link the shared drawing/pointer helpers
directly; do not start the exclusive hosted GEM service alongside it.

Acceptance: raw/optimized pixel oracles cover translated coordinates, partial
glyph clips, frame boundaries, retained row wrap, clear, multi-row scroll and
failure cleanup. Shell typing, CAT and EXIT work. Full-screen bitmap and standard
text modes remain selectable startup backends; their existing tiled presentation
and input routing pass focused regressions.
No extra handoff is added before the existing short-write presentation pass.

### DT3 Integrate ST input and measure pointer response

Acquire the pointer source in the presenter, retain its route/signal and reuse
the software pointer. Integrate pointer/caret ordering, keyboard focus and the
event endpoint. Complete the ST checkpoint above before adding gestures. Fix a
measured capture or delivery defect at its responsible layer; retain the existing
capture algorithm if the problem is downstream.

Acceptance: exact controller counts within the supported envelope, ordered
buttons, loss recovery, capture-time key/BREAK routing and balanced source
release. Record idle/scroll/cold-read latency and focused SIO coexistence.
Compare instrumented results with an unobserved replay. Report functional and
timing acceptance separately; unresolved responsiveness must remain visible
before progressing to dragging, rather than being mistaken for sampling success.

### DT4 Move windows with nonblocking drag state

Implement title hit testing, button capture, outline movement and release
commit. A drag remains captured outside the title bar; clamp its final position
onscreen and align it to the chosen grid. Coalesce obsolete outline positions
without discarding release. Cancel on loss, hide, retirement or explicit Escape.
Require release before rearming. Defer geometry mutation until active drawing
retires, while continuing input and retaining the gesture outcome.

Acceptance: repeated moves repair old/new areas exactly, including press/release
during scrolling, rapid reversal, release beyond the screen and loss while held.
No nested wait loop stalls other work. Measure outline response, release-to-
geometry commit and release-to-complete visible repair separately.

### DT5 Overlap windows from independent applications

Add a small Action! application Task with its own registration, retained
fill/text batch and event wait. Show it over the shell and exercise raising,
focus, obscured console output and exposure after movement or close. The client
can alternate bounded updates, waiting and a finite compute loop without GUI
calls; it must not run as a callback inside the presenter.

Acceptance: shell input remains usable while the other Task computes or waits;
the second window responds during shell output/I/O. Compare framebuffer and
scanout with independent complete recomposition after each scene transition.
Test both clients retiring first, a slow event consumer, invalid batches,
resource exhaustion and background/fully covered updates. Compare equivalent
one-client and two-client timing to expose starvation. Record peak Task use,
including commands/pipelines; resource shortages return cleanly.

### DT6 Complete shutdown and loaded development checks

Exercise close requests, event cancellation, pending paint/scroll, focus-route
retirement and source release together. Stop admission before draining requests;
keep storage retained through final replies and hardware quiescence. Cover
partial startup failure, blitter fault/watchdog recovery, reset-required holds
and clean OS return. A client port cannot disappear while the service can still
reply to it.

Acceptance: selected raw/optimized end-to-end runs pass stack/domain guards,
register/DP restoration, IRQ/NMI coexistence, exact pixels and bounded shutdown.
Repeat affected mouse timing under two-client repaint and physical SIO. Record
all timing targets, measured CPU/waits and outstanding limitations. A responsive
test panel alone is not evidence of independently scheduled applications.

### DT7 Package the desktop preview

Add an explicit desktop option to `tools/build_demo.py`; keep the standard
five-second OF816 autoboot into the shell/prime demo. The optional desktop
workload uses shell plus the second client and no primes. Package through the
existing demo flow with OF816 boot XEX, matching system disk, pinned ROM,
upstream notices, checksums and a short ST/port 1 guide. Keep intermediates,
manifests and test traces in the development directory, outside the distributed
`exec816-demo.zip`. Preserve any existing cartridge packaging support without
folding unrelated cartridge changes into desktop commits.

Acceptance: cold-boot the exact packaged media, demonstrate both clients,
pointer/focus/drag, a disk command and clean exit. Publish implemented contracts,
development evidence and remaining limits through the appropriate indexes.
Creating a local preview is this slice's deliverable; a public release and its
qualification/publication are separate actions.

## Timing acceptance and evidence

Use the [pinned platform](../../../toolchain/altirra-gem-vdi.json), including
`mouse_input.tooling` for the actual observer-capable emulator, and the
[compiler pin](../../../toolchain/actionc.json). Use PAL, 4 MiB CPU RAM and the
pinned VBXE profile. Record actual binary/media hashes and configuration in
every result; do not substitute the generic emulator hash for an override.

The following are proposed desktop targets, not historical results. DT0 records
the test sequences and sample count before changes. Use at least 100 paced
motion updates and 30 button/drag actions per applicable idle/loaded case,
varying frame phase. Report median, p95, maximum, event counts and raw samples.
Use base-cycle observations for sub-frame stages and actual scanout for visible
completion; Exec event ticks alone cannot resolve sampling latency.

| Measurement | Initial acceptance target |
| --- | --- |
| ST sampling gap | Strictly less than 1 ms, with exact counts for the supported electrical stimulus and no missing qualifying button edges. |
| Capture to visible pointer or drag outline | Idle p95 ≤40 ms, maximum ≤60 ms; during scrolling/cold I/O p95 ≤60 ms, maximum ≤100 ms. |
| Button delivery to the appropriate client or drag controller | Capture to consumption maximum ≤40 ms idle and ≤100 ms under the selected loads. Include queue pressure/loss separately. |
| Short shell echo | Same full-screen workload p95 within 10% of DT0 and maximum no more than one PAL frame worse; record framed-shell timings separately. |
| Move release to complete repair | At most 250 ms for the defined one-shell/two-window scenes; pointer/input processing must continue during repair. |

Record the longest interval between presenter input-service opportunities and
break down any failed visible target into capture, scheduling, CPU drawing,
DMA wait and scanout. Increasing sample frequency is justified only by capture
evidence; reducing a nominal timer rate requires a fresh transition/SIO proof.
Do not hide aliasing by changing sensitivity. Compare aggregate IRQ CPU share
as well as maximum handler duration; one worst-case call is not a utilization
measurement.

Passing capture correctness does not pass pointer responsiveness. Keep missed
targets open, identify their stage and add a focused follow-up slice if needed;
do not silently relax the target or rerun unrelated console optimization work.
The final preview must state which targets passed. Development evidence does
not establish physical-device or whole-system qualification.

## Memory and validation discipline

Target additional reserved bank-zero bytes: **0 fixed, 0 root/kernel, 0 per
existing public Task and 0 idle**, including guards, alignment and unused
capacity. Reuse the presenter's existing 2,560-byte pool and DP. The second
application occupies an existing pool; report its stack/DP occupancy separately
even when reservation growth is zero. Do not assume all eight public slots are
available to applications. Include shell, root/controller, filesystem, SIO,
presenter, test application and transient Processes in the ledger.

Keep window records, event queues, retained content, scratch regions and the
4,782-byte four-layer scene in upper RAM, never as large native-stack locals.
Report payload and reserved sizes separately, including staging buffers and
unused queue capacity. Audit the existing resident globals arena rather than
silently appending UI state. Keep one VRAM map for framebuffer, font atlas,
command storage and overlay saves, and the existing 4 KiB CPU aperture. No
backing surface or second aperture is assumed.

Follow the [development tier](../../contributing/testing.md#development-checks).
Each slice runs host checks, affected generators and focused emitted behavior;
raw/optimized coverage applies to Action!/C bridge and compiler-facing changes.
Extend existing console, Layers, input and VBXE fixtures where appropriate;
add proposed `tools/test_desktop.py` and `tools/measure_desktop.py` runners with
per-slice selection and independent geometry/pixel/controller oracles. Keep
production behavior free of injection or measurement hooks unless explicitly
selected by the test build.

Always check relevant guards, native register/DP restoration, ownership cleanup
and bounded completion. Interrupt, timer or scheduling changes require focused
deeper coexistence tests, including physical SIO and OS emulation entry. Read
the [platform contract](../../reference/platform.md) before changing platform
code; compiler defects belong in actionc with focused regressions. Update
reference pages only for implemented behavior and store development records
under `docs/development` with a linked history summary. Full release matrices
are reserved for release/qualification work, not every slice.

## Status

DT0–DT6 are implemented at the development tier; see the [execution record](../../history/desktop.md).
DT7 remains pending. DT3 passes functional capture/routing and pixel checks;
pointer p95 targets remain open. DT4 outline and move-repair targets also
remain open and must stay visible in the later loaded record. Full-screen echo meets the regression target against the frozen DT0
image. DT0 adds no runtime memory or Task.
