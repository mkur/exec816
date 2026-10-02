# Hosted GEM input and events implementation plan

[Implementation plans](../README.md) · [Design note](input-and-events-design.md) ·
[Current VDI contract](../../reference/gem-vdi.md) · [Roadmap](../../roadmap.md)

Status: I0–I2 implemented and development-checked; I3–I7 remain pending.
See the [implementation record](../../history/gem-input.md) and
[I0 evidence](../../development/gem-input-i0.json) and
[I1 evidence](../../development/gem-input-i1.json), plus
[I2 evidence](../../development/gem-input-i2.json). This plan implements
the design recorded in commit `ad50a42`. I0–I7 deliver native keyboard interaction
with a small VDI scene during physical SDFS reads, safe console handoff and a
renderer-owned cursor tested with injected pointer events. Physical mouse support
and AES are separately gated follow-ons, not prerequisites for shipping the
keyboard artifact and not capabilities claimed by completing I7.

Keep the G0–G6 workloads and their historical evidence. Add a new interactive
workload; do not replace the computing-peer regression with a GUI test. Preserve
the existing eight-Task pools, single renderer client and platform ownership
rules. No additional input Task, private GEM kernel service or new COP signature
is required. The implementation target is **0 fixed bank-zero bytes, 0 per public
Task and 0 for private idle**, including guards, alignment and reserved slack.

## Slice order and completion rules

| Slice | Depends on | Executable result |
| --- | --- | --- |
| I0 Media failure and shutdown | G6 | Wrong media restores text and reports an error; renderer stop needs no allocation after readiness; graphics disk has a distinct packaged name. |
| I1 Input records and bridge | I0 | Generated input layouts and C/native marshalling pass emitted layout and value probes without claiming hardware input. |
| I2 Shared producer admission | I1 | Serial and keyboard use one source-qualified public producer API; private console admission is removed. |
| I3 Reusable capture and console migration | I2 | One input implementation serves console and standalone consumers; focus, BREAK, loss and SIO coexistence still work. |
| I4 Interactive keyboard application | I3 | Two large Tasks run application and renderer; keyboard edits controls while root reads the disk. |
| I5 Cursor and pointer event semantics | I4 | Injected pointer/button events operate controls with exact cursor/background restoration. |
| I6 Concurrency and failure closure | I5 | Measured responsiveness, interrupt/context checks and bounded cleanup pass with real physical I/O. |
| I7 Documentation and artifact | I6 | The uninstrumented optional artifact, updated contracts and standard OF816 controls agree with the evidence. |

Treat each row as a separate reviewable change. Run its focused development
checks before marking it complete. Keep failed experiments under `build/`; write
passing records only after execution, with exact inputs and results. Do not
rewrite G0–G6 records to reflect changed source or new measurements.

## Interfaces selected for implementation

These are the initial ABI choices for I1–I3, not current public contracts. I1
must encode and check them through target-emitted layouts before I2 changes the
runtime. If a target layout cannot satisfy them, revise the manifest and this
plan together before migrating callers.

### Public producer binding

Extend `EXECPRODUCER` to `Bind(source,task,bits)`, `Release(source)` and
`Drain(source)`, with `SERIAL=1` and `KEYBOARD=2`. Source is a CARD; Task and mask
retain their current types. Bind returns a BYTE success value. Unsupported or
busy sources reject without mutation. Require a retained live target and its
allocated signal bits; hold both binding controller and target lifetimes until
release and wake retirement. Protect bound bits from FreeSignal for both sources.

Release stops source publication but does not authorize Task or signal reuse.
Drain retires queued wakes and removes an inactive binding. Draining an active
binding may deliver wakes but must not release its holds. Keep source-specific
mask/vector activation in bounded native platform helpers. Task admission,
retention and wake publication stay in general kernel policy; no driver queue
or GUI policy enters the kernel. Fixed source dispatch does not register arbitrary
application ISR callbacks.

Change the native argument schema in [tasks.json](../../../abi/tasks.json) and
advance its current packet profile tag from 6 to 7 in I2. Bind's native argument
payload is ten bytes: source at 0, three-byte Task pointer at 2, zero padding at
5, and four-byte signal mask at 6. Release/Drain carry the two-byte source.
Generate compiler outgoing-frame sizes and check them with emitted callers;
do not infer them solely from payload length. Keep the existing producer service
selectors and `COP #$50`; remove console's private `$F3/$F4` services. Update all
current callers in the same slice, with no compatibility profile.

### Input records and operations

Add `abi/input.json`, `tools/generate_input.py`, `lib/input/input.act` and
generated Action!/assembly/C definitions. Use two-byte record alignment and
little-endian fields. Record pointers remain native 24-bit addresses; Calypsi
entry points validate full huge-pointer values before narrowing. Leases, output
events and configuration records must fit validated writable/readable upper-RAM
extents within one CPU bank, with no field truncation or arithmetic wrap.

| Record | Bytes | Fields and offsets |
| --- | ---: | --- |
| InputLease | 32 | Existing TaskLease at 0; acquisition generation u32 at 12; published route u32 at 16; wake mask u32 at 20; state u16 at 24; zero flags u16 at 26; zero reserved u32 at 28. Opaque to callers. |
| InputConfig | 16 | Version u16 at 0; source u16 at 2; wake mask u32 at 4; two raw-key value/mask byte pairs at 8 and 10; filter count u8 at 12; flags u8 at 13; zero reserved u16 at 14. |
| InputEvent | 24 | Acquisition u32 at 0; route u32 at 4; tick u16 at 8; kind u8 at 10; flags u8 at 11; code u16 at 12; qualifiers u16 at 14; x/y i16 at 16/18; buttons u16 at 20; zero reserved u16 at 22. |

Version is 1. Event kinds are KEY=1, POINTER=2, BUTTON=3, LOSS=4 and CANCEL=5.
Event flags are TICK_VALID=1 and INJECTED=2; other bits are zero. KEY code holds
the raw scan byte, with SHIFT=1 and CONTROL=2 in qualifiers; Caps state and text
translation remain consumer policy. BUTTON code is the changed-button mask,
buttons is the resulting state; initially only LEFT=1 is supported. POINTER
has code zero. LOSS code identifies RAW=1, NORMALIZED=2 or HARDWARE=3. CANCEL
code distinguishes BREAK=1 and KEY_FILTER=2. Unused fields are zero.

Take timestamps from Exec ticks, not an assumed millisecond clock. A durable
mailbox without a retained capture timestamp clears TICK_VALID; do not invent
a capture time when draining it. Latency measurements use native KEY records
with valid timestamps. All elapsed intervals must remain below half the tick
range, including tests across wrap.

InputConfig accepts only source KEYBOARD and flag CAPTURE_BREAK=1 initially.
Filter count is 0–2; each active mask is nonzero, each value has no bits outside
its mask, and unused pairs are zero. Copy configuration into resident storage
before activation; do not retain a caller's temporary configuration pointer.
Use Escape value `$1C`, mask `$3F`, plus BREAK for the GUI. Preserve the console's
Ctrl-C pattern value `$92`, mask `$BF`, plus BREAK. IRQ work is a bounded raw-code
match and route latch, not character translation or a GUI callback.

Use result codes OK=0, EMPTY=1, BUSY=2, BAD_ARGUMENT=3, INVALID_OWNER=4,
EXHAUSTED=5, UNSUPPORTED=6 and NO_MEMORY=7. Lease states are FREE=0,
ACQUIRING=1, ACTIVE=2 and RELEASING=3. No operation blocks waiting for another
owner. The planned library surface is:

| Operation | Contract |
| --- | --- |
| Acquire(lease,config) | Current Task becomes the exclusive consumer; retain its signal and identity before enabling capture. Begin with route zero, which discards unaddressed input. |
| CreateRoute(lease,flags,outTag) | Reserve one of sixteen route slots and return a nonrepeating tag; initial flags are zero. No DOS/console pointer is stored in the input layer. |
| PublishRoute(lease,tag) | Atomically select an admitted route, or zero to stop addressed capture. Older queued records keep their original tag. |
| RetireRoute(lease,tag) | Release an unpublished tag only after its records/notices are drained; return BUSY for pending references or the currently published tag. |
| Discard(lease,tag) | Clear captured ordinary input and its loss state for this route, preserving durable cancellation. Later arrivals survive the clear boundary. |
| Pending(lease,outMask) | Return status and a work mask: DATA=1, LOSS=2, CANCEL=4. This observation does not authorize clearing its wake signal. |
| Take(lease,event) | Copy one complete event or return EMPTY without modifying the output; consume durable cancellation before loss and ordinary records. |
| Release(lease) | Stop capture, retire routes and wakes, then release the binding and lease; only successful completion permits signal/storage reuse. |

Acquire, Take and Release are consumer-only. Route control, Discard and Pending
may execute in another Task through the same live lease as bounded driver
operations, serialized with Forbid and native publication guards. This is
required by console focus/foreground calls that run on their callers' stacks.
Validate the address-stable lease and retained consumer on every operation;
sharing this authority is explicit in the shared-address-space model. It does
not transfer consumption rights. A copied lease or stale acquisition fails.

Use a monotonic 32-bit acquisition counter and the existing route form
`(epoch << 4) | slot`, with sixteen slots and a 28-bit epoch. Neither wraps;
exhaustion rejects new admission. Preserve raw keyboard records at eight bytes
(code, kind, tick, route), 64 slots in upper RAM. Stamp the acquisition into the
24-byte output on Take: this is safe only because Release retires the whole raw
ring before another acquisition. Test that boundary explicitly. Retain sixteen
cancel and loss mailbox bits plus generic route tags; IRQ never resolves console
units or foreground pointers. Take atomically acknowledges a mailbox item so a
later capture remains pending.

### Application control and rendering

Keep control records in `ports/gem4xe/interactive/`, separate from public input.
Generate their shared Action!/C layout. Use 32-byte messages: existing 16-byte
Exec Message, version u16 at 16, command u16 at 18, session u32 at 20, value u32
at 24, result u16 at 28 and zero reserved u16 at 30. Commands are START=1,
PROGRESS=2, STOP=3, DISK_DONE=4 and EXIT=5. Version is 1; session is a nonzero,
root-issued generation that refuses reuse/wrap. A root-owned boot descriptor
supplies validated port addresses and retained Task identities before readiness.

Preallocate four distinct slots: root progress, root START/STOP control, root
DISK_DONE and application EXIT notification. Reply once to each accepted message.
START/STOP share a slot only after collection of the prior reply. Progress can
coalesce only while root owns its slot; never mutate an in-flight message. STOP
admission is separate from application retirement, so its reply cannot create a circular
wait on disk completion. Durable exit state and a retained signal notify root
even while root is inside DOS. Root checks that state before the next file call.

EXIT requests root to stop file work; it is not the final removal notification.
After cleanup, root collects all root-originated replies, releases its application
lease and replies to EXIT. The application retains a self lease before readiness
and collects that reply only after its own input/renderer resources are settled.
Under Forbid it publishes retirement, signals the still-retained root, releases
its final holds and removes itself before root can resume. Use the existing
release/notify/remove protocol; no live external lease may still prevent
self-removal. On root-requested stop the application still sends EXIT, so both exit directions use this same
handshake. Keep the notification storage alive until root observes retirement.

Add `GemTryCollect` in I4: validate and collect the exact pending reply without
waiting, returning a separate ready flag and status. Empty queues retain packet
ownership and leave sequence/session unchanged. An unexpected reply is a protocol
fault, not a reason to free storage. Keep the existing blocking helper for
startup/shutdown and other synchronous callers, sharing collection logic.

In I5, advance the private GEM packet revision to 2 and add service CURSOR=5.
It uses the existing 156-byte header plus an eight-byte payload: x/y i16,
visible u16 restricted to 0/1, reserved u16 zero. Require total length 164,
command_count zero, the live generation and next sequence. Coordinates identify
the fixed top-left hotspot within x=0–639, y=0–239; reject out-of-range requests
without mutation. A successful fenced cursor request advances sequence, with
completed_count and reply_words zero. Unknown services and old packet revisions
fail explicitly. Rebuild all fixtures; no legacy packet path is retained.

## I0 Media failure and shutdown

Change [gem_concurrent_launcher.act](../../../tests/programs/gem_concurrent_launcher.act)
to record ordinary media failures instead of aborting inside an owned display.
Cover Open failure, short Read, wrong bytes and Close failure. Preserve the first
error while finishing cleanup. Close an opened file and release DOS context;
collect accepted rendering, close the workstation and stop/dispose the service.
After display release, restart the console and display the result for a bounded
250-PAL-tick hold before OS return. Do not perform a metadata preflight that
warms the first physical read.

Refactor [GemServiceStop](../../../ports/gem4xe/service/gem-client.c) to use a
stop reply port and packet reserved by service startup, before readiness. Free
them on every partial-startup failure, or after exact stop collection. Preserve
the ability to stop a service with an accepted request still pending; that reply
remains the client's collection obligation. A permanently busy blitter retains
the current reset-required ownership. No timeout invents successful retirement.

This moves the existing rounded 192-byte stop allocation into the steady service
lifetime: the current 2,464-byte service/client heap subtotal becomes 2,656 before
new input allocations. Measure actual record growth and allocator rounding too.
Change current failure fixtures for stop-port/stop-packet allocation to startup
rollback cases; add real heap exhaustion after readiness proving stop still
works. Historical G5 evidence stays unchanged.

Copy the internal graphics `system.atr` to distributed `graphics.atr` in
[build_gem_artifact.py](../../../tools/build_gem_artifact.py). Change the graphics
whitelist in [package_demo.py](../../../tools/package_demo.py), package tests,
[distribution guide](../../gem-vdi-distribution.txt) and [run guide](../../guides/gem-vdi.md)
together. Root `system.atr` keeps its standard role.

Acceptance: extend the concurrent runner with wrong standard disk, no disk,
short/corrupt file and stop-under-exhaustion cases in raw/optimized mode. Verify
readable error scanout and normal cleanup for terminal media errors,
all guards, display/OS restoration and allocator ownership. A missing drive can
produce an uncertain SIO timeout: retire graphics and console, display the reset
requirement, and retain the offline bus at `$FF93` under the existing
[device contract](../../reference/device-io.md). I0 execution exposed this
exception to the original normal-return requirement; clearing the offline latch
would falsely claim that late serial traffic had quiesced. Check one successful
physical workload as a control. Any refreshed ZIP goes through `build_demo.py`.

## I1 Input records and checked C entry

Generate the selected InputLease, InputConfig and InputEvent layouts, constants,
and an offset/size probe from `abi/input.json`. Add `c/include/exec/input.h` and
`c/calypsi/input.c`, `input.s`, `input-bridge.inc` and `input-layout.c`, following
the [display bridge](../../../c/calypsi/display-bridge.inc). Put public declarations
under the existing interface license rules; update the licence map if needed.

Extend [build_gem_vdi.py](../../../tools/build_gem_vdi.py) or its shared C helpers
to link a focused input ABI probe. Check upper-bank structures, alignment,
full-width pointer rejection, bank-end extents, register preservation and
Action!/C return values using emitted code. The probe may round-trip fixture
values but must not provide success stubs for unimplemented Acquire/Release.
Do not change the live producer packet tag until I2 migrates all callers.

Acceptance: generator `--check`, meaningful malformed-layout/pointer host checks,
raw/optimized emitted layout/value probes, guarded C context and clean return.
Record the exact ABI map and compiler/runtime hashes as I1 evidence.

## I2 Shared producer admission

Implement source-qualified binding in [task-wakes.inc](../../../lib/exec/task-wakes.inc),
Task removal/signal checks in [taskpolicy.act](../../../lib/exec/taskpolicy.act),
and the native stubs/posting path in [tasks.s](../../../platform/altirraos/tasks.s)
and [signal-irq.s](../../../platform/altirraos/signal-irq.s). Reuse the existing
serial/keyboard binding storage where possible. Source descriptors remain fixed
resident data; registration must not accept arbitrary hardware callbacks.

Migrate [siodriver.act](../../../lib/io/siodriver.act), console startup/teardown,
producer probes, Task-lifetime and CreateTask fixtures in one change. Remove
ConsoleProducerControl and private admission constants from
[task-console.inc](../../../lib/console/task-console.inc) and
[console.json](../../../abi/console.json), retaining unrelated console setup/name
helpers. The console can still use its current capture implementation in this
slice, through the new public KEYBOARD binding. I3 replaces that capture boundary.

Update [generate_tasks.py](../../../tools/generate_tasks.py),
[generate_console.py](../../../tools/generate_console.py), generated outputs,
[native_program.py](../../../tools/native_program.py) import marshalling and all
affected C/native ABI checks. Audit generators as well as source callers: the
current Task generator contains SIO producer source checks. Reject old profile
tags; do not silently interpret the old Bind payload under the new schema.

Acceptance: bind busy/unsupported/unretained targets, wrong controller release,
FreeSignal/removal while bound, active/inactive Drain, pending wakes, signal/Task
reuse and rollback. Run focused Task/SIO lifetime and console-input controls in
both compiler modes, including keyboard/SIO acquisition and release orders.
Prove NMI cannot expose a partial binding and record all producer metadata costs.

## I3 Reusable capture and console migration

Move keyboard claim/release, raw ring and native/emulation capture from
[console.s](../../../platform/altirraos/console.s) into a reusable input adapter.
Split input enablement from `CONSOLE_NATIVE`: a graphics build must retain
keyboard routing when no console worker owns the display. Keep text presentation
helpers and recovery in the console adapter. Update both ordinary IRQ routing
and SIO's interleaved keyboard route; preserve serial-first ordering and bounded
POKEY accesses.

Implement lease acquisition, generic route registration, publication, Take,
Discard and release in `lib/input/`. Claim configuration and route state before
publication; unwind failures in reverse order. Forbid protects Task-side tables;
short native IRQ-masked transactions protect multiword publication. NMI may tick
but cannot switch an interrupted masked transaction. Neither interrupt path
touches MEMAC, VRAM, an application object or a DOS pointer.

Migrate console registration/focus/foreground paths to the generic route APIs.
The console keeps unit, scope and bound/unbound policy in its own route records,
indexed by the admitted tag's low four bits. When a scope ends, remove its target
immediately but retain its tag until captured input/notices have drained. Preserve
ordinary console typeahead; only explicit CLEAR or session shutdown discards it.
Reclaim only when generic capture says retirement is complete. Replace direct
reads of `CS_CAPTURE` with the library's bounded observations; do not maintain a duplicate
keyboard queue for console compatibility.

For CANCEL, the generic producer publishes one durable notice instead of both
a notice and ordinary key record. Console policy converts an unbound notice
into one byte `$03`, delivers a bound notice to its foreground scope, and drops
retired-scope notices. This preserves behavior without duplicate cancellation.
Discard/console CLEAR preserves bound cancellation, and later loss cannot be
erased by an earlier clear. GUI LOSS invalidates its edit/gesture sequence;
recovery must not manufacture a button release or activation.

Acceptance: add `tools/test_input.py` and a standalone Action!/C capture fixture.
Cover copied/stale leases, owner/controller permissions, route exhaustion,
acquisition wrap refusal, same-tick ordering, raw FIFO saturation, cancellation
with no pending read, publication/clear/release interrupts and two acquisitions
using the same storage. Exercise the no-lost-wakeup boundary with events arriving
just before Wait. Keep a bounded turn runnable when records remain after its
drain quantum; never wait solely because the previous signal was consumed.

Run the existing console input, focus, foreground BREAK, startup rollback and
stop/restart cases affected by migration, in raw/optimized mode. Include physical
SIO in both start/stop orders, held keys across SIO phases and selected native/
emulation capture paths. Check vectors, masks and shared SKCTL restoration.
An inactive source alone does not prove queued wakes or retained signals retired.

## I4 Interactive keyboard application

Add `ports/gem4xe/interactive/` for the bounded UI/event loop and a new
`tests/programs/gem_interactive_launcher.act`. Root creates the C application
with 2,560 bytes; that application starts the renderer with 2,560 bytes before
small services are admitted. Both remain retained through final notifications.
Record every live Task and its selected pool; reject a third large-Task request
cleanly in an admission control case.

The application is the renderer's sole owner, client and stop authority. Root
closes text handles, releases DOS context, stops the console and authorizes the
cold display baseline before sending START. The application opens graphics,
acquires input, creates/publishes its route, paints the initial scene and replies
ready. Failure at any step releases what that step acquired before replying.

Build three focusable controls: a 24-character text field, a color/counter button
and Exit, plus a read-only disk progress indicator. Tab cycles focus, printable
ASCII and Backspace edit the field, Return activates the focused button, and
Escape/BREAK requests exit. Use existing font and drawing operations; no AES
source extraction or file-loaded resource is needed.

Process at most eight input events, available control messages and one exact
render completion per turn. While a packet is pending, preserve it and accumulate
dirty UI state. Start with at most four VDI commands and eight glyphs per
interactive packet; split larger initial/redraw work into these quanta. These
are workload limits, not a reduction of the public VDI allowlist. Yield between
busy turns and wait only after every source is observed empty. Do not clear a
notification after its queue observation.

Root reads `D1:DATA.BIN` cold in 128-byte chunks and verifies the existing 2 KiB
pattern. It sends bounded progress and DISK_DONE messages; disk completion leaves
the scene interactive until Exit/Escape. Root can then wait for the application
without preventing it from collecting rendering or stopping its service.
Stop during a file call takes effect before the next call; root owns and settles
the current DOS operation. For automated tests, send explicit input and require
bounded retirement; the human session's idle wait is intentional.

Acceptance: generated control-message layouts, keyboard-to-control state and
pixels, input while a render reply is pending, display/input busy conflicts,
clean startup failure, early/late Escape, root-requested stop and disk-error
cleanup. Confirm client/supervisor calls originate from the application Task.
Keep the G5 computing peer as a separate regression, not a third large GUI Task.

## I5 Cursor and injected pointer behavior

Implement CURSOR validation, nonblocking client preparation and a renderer
callback through [gem-vdi.json](../../../abi/gem-vdi.json), its generator,
service validation and [gem-vbxe.c](../../../ports/gem4xe/adapter/gem-vbxe.c).
Initialize cursor visibility to hidden on every OPEN; no cursor state survives
generation replacement. Hide/restore before every scene update, then save and
redraw at the latest accepted position. Validate the entire request first.
Cursor work does not alter VDI pen, clipping or text attributes.

Reserve `$37000–$373FF` in [vbxe-vram.json](../../../platform/altirraos/vbxe-vram.json):
256 bytes saved background, two 256-byte expanded mask planes and 256 bytes
reserved slack. Use a fixed 16×16 mask with hotspot (0,0). At odd x positions,
cover up to nine packed bytes per row and preserve neighboring nibbles. Clip
at all screen edges. The CPU staging page remains the existing upper-RAM page;
never borrow live glyph scratch. Fence before scratch reuse, reply or release.

The application queue holds 32 InputEvent records. A test-only producer sends
copied, validated pointer events carrying the active acquisition and route,
using the same bounded queue publication path as future backends. Reject stale
tags, unsupported buttons and out-of-range coordinates. Mark injected events;
compile out the producer and its entry points in production. Never make tests
pass by writing control state or framebuffer memory directly.

Coalesce only adjacent motion with identical session and buttons. A press arms
one enabled control; a matching release over it activates once. Release elsewhere,
loss or cancellation disarms it. Queue overflow latches LOSS separately, drops
the incomplete sequence and requires a fresh released state before rearming.
Test an event arriving during loss acknowledgment and while the queue is full.

Acceptance: independent exact pixels for show/hide/move, odd/even x, every edge,
stationary-cursor scene updates and generation reopen. Check malformed CURSOR
requests leave scene, attributes, sequence and cursor unchanged. Exercise failure
during restore/save/draw and retain reset-required behavior when quiescence fails.
Button sequences must remain correct while a cursor packet is outstanding.

## I6 Concurrency and failure closure

Add `tools/test_gem_interactive.py` with raw/optimized builds, named case selection,
and replay against an existing artifact. Observe native matrix key capture,
application progress and visible pixel change during live physical SIO, using
the existing pinned graphics configuration and `generic56k` profile. A pending
DOS request or uncollected renderer reply is insufficient evidence of overlap.
Record serial phase and terminal-post counts at input and render observations.

Measure capture-to-first-visible-control-update latency for the small redraw
quanta. Require at most sixteen PAL ticks in the selected healthy workload in
both modes, including wrap tests. Measure maximum, not only average. Record
capture, queue consumption, submission, completion and scanout points separately;
do not include injected pointer timestamps in a physical-keyboard claim. If the
limit fails, reduce interactive work or fix wake scheduling and rerun the affected
case. Changing the target requires an explicit design/plan revision.

Exercise real allocation/signal exhaustion at startup boundaries, both large
pools occupied, input/display BUSY, full raw/normalized queues, stale sessions,
Escape during rendering and disk I/O, wrong/missing/short/corrupt media, normal
stop, recoverable hardware timeout and permanent busy. Include heap exhaustion
after readiness with successful collection and shutdown. Root and application
must not wait on each other's final acknowledgment in a cycle.

Snapshot full interrupted C context in both application and renderer, lower-DP
preservation, every stack guard and OS state. Measure high-water marks without
refilling live stacks. Verify no Task lease, route, producer signal, message,
file or mapped aperture remains after a successful exit. For permanent busy,
verify required resources remain retained with `$FF93`, rather than claiming
cleanup. Preserve immutable event transcripts and pixel/palette expectations.

After diagnostic cases, repeat the keyboard scene and orderly exit on the
production image without injection hooks, substituted hardware status or
target-side timing rendezvous. Observer timing must not be the only reason a
case passes. This is focused development evidence, not platform qualification.

## I7 Documentation and artifact

Add the current input contract under `docs/reference/` only after implementation
passes. Update signal/producer, console and GEM references, the port README,
guide and documentation indexes. Record the implemented discussion in history
and leave links from the plan. State keyboard controls, measured limits, the
exact graphics disk/XEX pair and the lack of physical mouse or AES support.

Build the interactive optional payload through `tools/build_demo.py --gem-vdi`
in a fresh output directory such as `build/gem-input/i7-demo`. Keep the standard
OF816 XEX, its five-second shell/prime autoboot, root disk, pinned ROM and notices.
The optional XEX may retain `gem-vdi/Exec-gem-vdi.xex`; its new guide explains the
interactive scene and matching `gem-vdi/graphics.atr`. The G5 font workload stays
available through its development runner. Test the exact packaged interactive
image, not a separately rebuilt approximation.

Verify ZIP whitelist, checksums and notices. Maps, manifests, extracted source
and test results remain outside the ZIP. Run affected OF816 automatic/Forth-command
shell routes, input, disk and exit controls after the shared keyboard migration.
Do not expand this into the full release matrix unless qualifying a release.

Write new `docs/development/gem-input-iN.json` records for completed slices,
including parent/source revisions, ABI/pin/compiler hashes, maps, selected cases,
latency, pixels, lifetime outcomes and exact artifact hash where applicable.
Validate records with a small recorder that rejects missing/failed inputs and
stale hashes. Never infer a passing result from an old G6 screenshot or record.

## Focused validation and memory accounting

Follow the [development tier](../../contributing/testing.md). Run the host suite
after each code slice and relevant generators with `--check`. Raw means Action!
raw NIR with Calypsi `-O0`; optimized means optimized NIR with Calypsi `-O2`.
Use compiler/ROM/emulator inputs already pinned for GEM; record any necessary
pin change and rerun the boundary it affects. Do not modify donor code to hide
a compiler defect or change kernel behavior for a single fixture.

| Changed boundary | Existing controls to reuse |
| --- | --- |
| Producer admission and Task/signal lifetime | `tools/test_task_lifetime.py`, `tools/test_sio_lifetime.py`, affected CreateTask and signal ABI cases. |
| Capture, focus and cancellation | `tools/test_console_input.py`, `tools/test_console_focus.py`, `tools/test_foreground_break.py`, startup/lifetime cases. |
| Service stop and renderer packets | `tools/test_gem_service.py`, selected `tools/test_gem_concurrent.py` cases. |
| Cursor, mapping and failure recovery | `tools/test_gem_render.py`, affected `tools/test_gem_display.py` cases. |
| Final packaging and ordinary user input | `tests/test_demo_package.py`, `tools/test_of816.py`, exact-image interactive replay. |

New input and interactive runners should accept `--mode raw|opt`, `--case NAME`,
`--output DIR` and an explicit replay option. Do not assume existing runners use
those flags: console runners use `--case raw|opt` and have different mode/order
arguments. Select the affected cases once, reuse unchanged images where the
runner validates inputs, and broaden only for failures or a newly affected boundary.

Every slice compares complete `memory.json` reservations against its baseline,
separating fixed, each public pool and private idle. Keep 56,128 total reserved
bank-zero bytes and 9,408 free after startup as the eight-Task target. Stack sizes,
DPs, external guards, resident segment padding and the 4 KiB CPU aperture all
count. Additional code inside reserved upper banks is still recorded in maps.

| Item | Budget or required measurement |
| --- | --- |
| GUI input FIFO | 32 × 24 = 768 upper-RAM bytes, plus measured indices and durable loss/cancel state. |
| Lease/config/event scratch | 32/16/24-byte records; count static instances and allocation rounding, not just types. |
| Raw capture | 64 × 8 = 512 payload bytes; migrate existing storage and separately count route/filter/binding metadata. |
| Control messages | Four preallocated 32-byte slots = 128 payload bytes; ports, boot descriptor and leases are additional. |
| Service stop reserve | Existing rounded 192 bytes moves to steady lifetime; measure all new server fields and allocations. |
| C image | Start within the already reserved `$0C`/`$0D` code/data banks; overflow requires a checked upper-bank map revision. |
| Cursor VRAM | +1,024 bytes: 108,032 total reserved, 416,256 unassigned out of 524,288. CPU storage is separate. |

Report stack peaks/headroom for both large Tasks and root/kernel/idle/service
workers. Existing G5/G6 peaks do not bound new paths. On an exceeded stack or
bank budget, revise placement or implementation before accepting the slice;
do not silently enlarge pools or omit guards. This plan itself changes reserved
bank zero by **0 fixed, 0 per public Task and 0 private idle bytes**.

## Physical pointer and AES follow-on gates

After I7, prepare a separate physical-input slice selecting one exact device,
port and protocol. Pin emulator device settings, input injection/observation
commands and source hashes before making a compatibility claim. Audit PIA/POT,
SKCTL, AUDCTL, timer and IRQ ownership against active SIO. Prefer a backend that
can meet its sampling bound without taking SIO's timers; a frame-polled absolute
or counter device remains a candidate until tested. Measure maximum missed motion,
button fidelity, keyboard latency and serial errors together. Unsupported hardware
must reject cleanly. Keep donor quadrature timer installation excluded unless a
shared timing design and executable coexistence evidence justify it.

AES needs its own bounded plan after the event/cursor interface is stable. Select
one object tree/dialog and a precise operation allowlist; audit all near pointers,
global state and memory ownership before importing source. Specify pending waits,
timer wakeups, cancellation and wrap-safe deadlines. Current Exec Wait has no
timeout, so ordinary Sleep cannot stand in for an input-or-timer wait. Neither a
VDI-drawn button nor injected pointer success establishes AES, GEMDOS or desktop
compatibility.

## Plan preparation checks

Preparation checks the current design, producer/capture/service code, generator
and runner entry points, documentation links, record offsets and budget arithmetic.
No emitted code or demo is rebuilt for this documentation-only change, and no
new API constants or executable evidence are published until their slices run.
