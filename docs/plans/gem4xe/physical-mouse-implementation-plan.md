# Physical mouse implementation plan

[Implementation plans](../README.md) · [Design note](physical-mouse-design.md) ·
[Current input contract](../../reference/input.md) · [Roadmap](../../roadmap.md)

Status: proposed, 2026-10-02. M0–M6 are pending. Implement the configured
**ST mouse on joystick port 1**, with motion and the left button, using Altirra's
existing controller. The endpoint is the current interactive GEM scene accepting
mouse and keyboard input during physical SDFS reads and returning cleanly to text.

This plan follows the completed I0–I7 milestone at `a9da461`. It does not add a
mouse model, require a new ROM, or import GEM4XE's standalone interrupt setup.
Shared timer ownership is the first runtime change. Amiga decoding can later use
the same capture path, but it is outside these slices.

## Slice order and completion rules

| Slice | Depends on | Executable result |
| --- | --- | --- |
| M0 Device configuration and observation | I7 | The existing ST/port 1 model produces measured PORTA/TRIG0 changes; deterministic stimuli and the current SIO baseline are recorded. |
| M1 Shared timer ownership | M0 | SIO and a bounded diagnostic sampling demand share timer 1 through native and emulation paths, including startup and teardown in either order. |
| M2 Input ABI and source state | M1 | Generated version-2 configuration and source-aware lease plumbing pass emitted Action!/C checks; current keyboard clients are migrated. |
| M3 Native mouse capture | M2 | An ordinary Task receives pointer/button/loss records alongside a live keyboard lease, with safe wake, release and reuse. |
| M4 Interactive integration | M3 | Physical controller events drive the existing cursor and controls while disk work continues; partial startup and exit unwind correctly. |
| M5 Coexistence and failure closure | M4 | Sampling, response latency, serial deadlines, context restoration and bounded failure paths pass the declared development envelope. |
| M6 Contracts and artifact | M5 | Current documentation and the optional production demo match demonstrated mouse behavior; standard OF816 controls still pass. |

Commit each slice after its focused checks pass. Keep every commit buildable;
label facilities that remain unsupported at that boundary. Do not retain old ABI
profiles or compatibility implementations. Update generators, callers and tests
together. Compiler defects belong in actionc with focused regressions.

Write each slice's reports under `build/gem-mouse/mN/`, then freeze a passing
record as `docs/development/gem-mouse-mN.json`. These are future outputs, not
existing evidence. Add a history page when execution starts and link each record
there. Preserve the G0–G6 and I0–I7 records and original hashes.

## Inputs and boundaries

Use [actionc.json](../../../toolchain/actionc.json),
[GEM inputs](../../../ports/gem4xe/inputs.json) and
[altirra-gem-vdi.json](../../../toolchain/altirra-gem-vdi.json). Keep the pinned
PAL 800XL/65C816 ×8, VBXE configuration, DLI disabled, and physical SDFS profile 4
with 128-byte sectors as the primary development workload. Record all overrides.

Extend the emulator pin with an explicit mouse section: ST model, human-facing
port 1/internal index 0, enabled input map, sensitivity and acceleration settings,
host capture behavior, conflicting mappings disabled, source hashes, and the
actual automation commands used. Preserve the ROM hash. If bridge tooling needs
changes, record its patch/build provenance and new binary hash separately from
the existing device model. Update relevant emulator build instructions as well.

No extra input Task, third large stack, new COP signature, AES import or window
manager is proposed. Queue and lifecycle policy remain in the input/SIO drivers;
generic kernel producer admission retains Tasks and signal bits. New combined
kernel operations, if needed, require a reusable public ABI and a plan update.

## Interfaces selected for implementation

These are proposed M2/M3 contracts. Current reference pages continue to describe
the implemented version until the corresponding slice passes.

### Generated public records

Keep the eight existing INPUT operations and their checked C/native bridge.
Keep InputLease at 32 bytes and InputEvent at 24 bytes, with existing field
offsets, event kinds and status values. Add `SOURCE_POINTER=3` beside KEYBOARD=2
in INPUT and `POINTER=3` beside SERIAL=1/KEYBOARD=2 in EXECPRODUCER.

Set InputConfig version to 2 and size to 32 bytes, aligned to two bytes:

| Offset | Field | Type / meaning |
| ---: | --- | --- |
| 0 | version | u16, exactly 2 |
| 2 | source | u16, KEYBOARD=2 or POINTER=3 |
| 4 | wakeMask | u32, nonzero allocated signal bits of the consumer |
| 8–13 | filter fields | Existing two value/mask pairs, filterCount and flags, at their current offsets |
| 14 | reserved | u16, zero |
| 16 | pointerProtocol | u16, ST=1; zero for keyboard |
| 18 | pointerPort | u16, 1; zero for keyboard |
| 20 | initialX | i16 |
| 22 | initialY | i16 |
| 24 | maxX | i16, inclusive, origin is zero |
| 26 | maxY | i16, inclusive, origin is zero |
| 28 | reserved2 | u32, zero |

Keyboard configuration retains its existing filter/flag rules and requires
bytes 16–31 zero. Pointer configuration requires bytes 8–15 zero, ST/port 1,
nonnegative maxima and initial coordinates within bounds. The GUI supplies
maxima 639/239. Use one transition per pixel and no acceleration initially.

Check the full 32-byte writable upper-memory extent before reading configuration;
reject odd addresses, bank crossings, absent/read-only memory and huge values
outside 24 bits before narrowing. Malformed fields/version return BAD_ARGUMENT;
unknown source/protocol/port returns UNSUPPORTED without hardware changes.
BUSY means the requested source or required hardware is owned incompatibly.
Retain existing INVALID_OWNER, EXHAUSTED and NO_MEMORY meanings.

M2 updates generated records, layout probes, all keyboard initializers and the
C bridge together. It may validate pointer configuration while Acquire still
returns UNSUPPORTED until M3 installs the real backend; that is a documented
slice boundary, not a second ABI. Rebuild all affected programs. Producer call
packets retain their current shape; do not change the gateway packet tag merely
for a new source value unless another actual packet change requires it.

### Source identity and retirement

Replace the singleton lookup in INPUT with two fixed source descriptors. Locate
an existing lease by its address in those descriptors, then validate its complete
identity; do not trust caller-writable fields to select arbitrary storage.
Lease flags/reserved remain zero. Each source has its own route slots, capture
state and notices. A single monotonic u32 acquisition allocator gives leases
distinct identities across sources; refuse exhaustion before wrap. Keep the
existing nonrepeating 28-bit route epoch per source.

Acquire/Take/Release remain consumer-only; route operations keep their present
shared-authority rules. Bind, Release and Drain extend the existing public
retention protocol to POINTER. Update every source enumeration in Task removal,
signal freeing, shutdown and wake retirement, not just Bind's switch statement.
Direct producer binding uses the fixed ST/port 1 backend with route zero until
INPUT publishes a route; it does not register an arbitrary callback.

Publishing a new pointer route seeds its counter baseline and requires a fresh
released-button observation. Route zero discards addressed events while still
tracking electrical phases. Discard and hardware loss establish a discontinuity:
old ordinary records must not rearm a gesture after its loss notice. Release
stops publication, purges records/notices, drains wakes and retires ownership
before lease, signal or storage reuse. Keyboard release never releases pointer
capture, and pointer release never releases keyboard or active SIO work.

### Capture record and event expansion

Generate a private 24-byte pointer sample record, separate from InputEvent:
acquisition u32 at 0, route u32 at 4, tick u16 at 8, kind u8 at 10, buttons u8 at
11, cumulative X/Y i32 at 12/16, discontinuity epoch u16 at 20, and flags u16 at
22. Define motion and state/baseline kinds and permitted flags in the native
manifest. Button state initially permits LEFT only. Use 32 records and durable
per-route loss storage; no allocation occurs in interrupt context.

Track every legal electrical transition. Publish only changed motion/state or
a required baseline. Adjacent motion snapshots may coalesce within matching
identities, epoch and button state. Stop coalescing at a reversal on either axis
so clipping retains the intervening extreme position. Preserve the earliest
outstanding motion tick for conservative latency accounting; button records
retain their own capture tick. Never coalesce across a button transition or loss.
Check signed counter limits before overflow and establish a loss/rebase boundary.

The discontinuity epoch prevents queued pre-loss samples from restoring stale
state. Refuse epoch reuse while it can alias a retained record; exhaustion
disables addressed capture with durable loss until reacquisition. A baseline
record resets the consumer reference without moving the pointer. Do not infer
missing transitions from timer interrupt counts, which can themselves coalesce.

InputTake converts counters to bounded coordinates in Task context. If a state
sample contains both movement and a button transition, return POINTER with the
previous button state first, then retain a BUTTON with the new state as bounded
pending output for the next Take. This matches the existing gesture handler:
putting the new state on POINTER would consume the edge before BUTTON arrives.
Pending reports that output; route retirement, Discard, loss and Release account
for it too.
Neither event can cross a route/session discontinuity. Use checked arithmetic
for differences and clipping; an unrepresentable delta causes loss rather than
signed overflow. Hardware events have INJECTED clear, TICK_VALID set and
zero qualifiers; durable loss has tick zero and TICK_VALID clear.

## M0 Device configuration and observation

Use the existing `Mouse -> ST Mouse (port 1)` map. Add a small emitted observation
fixture that reads PORTA/TRIG0 and records real transitions, without claiming a
complete mouse driver. Confirm both axes/signs and left-button levels; read the
low nibble and TRIG0, not port 2. Record GTIA trigger-latch state and prove the
observation does not change PIA direction, port 2 or paddle/serial registers.

For deterministic automation, first reuse suitable existing input-map controls.
If needed, add narrow scheduled host-motion/button commands through Altirra's
existing input manager/controller, plus passive observation of emitted phase
transitions. Also retain the ordinary host-mouse path for a manual production
check. Direct PIA phase injection may test decoder edge cases, but cannot replace
the existing-controller path in acceptance.

Record two timestamps for latency: controller transition and Exec capture.
Use emulated time, not delays between host bridge commands. Keep an independent
expected transition/count trace; do not derive the oracle from the target's
decode table. A complete cycle must remain visible to the observer even when
target sampling misses it.

Run selected current SIO alarm/deadline and interactive keyboard cases with the
mouse mapping enabled. Record the pre-change baseline, including source/binary
hashes, exact disk contents, IRQ timing and stack use. The initial acceptance
target is 1,000 legal transitions per second per axis, spaced at least 1 ms
apart, and button down/up levels each held at least 10 ms. This requires a
worst sampling gap strictly below 1 ms during the declared workload. Record
these bounds before M1 and test the ordinary host mapping, including its bursts,
separately. They are proposed acceptance limits, not measurements or a guarantee
for arbitrary mouse speed. Do not weaken them after a failure merely to mark
the driver passing; a changed target needs an explicit design/plan revision.

**Gate:** repeatable controller traces and passing baseline cases. No production
mouse-support claim yet. Commit the pin, observation tools and M0 record.

## M1 Shared timer ownership

Add a fixed platform timing component, preferably an upper-RAM assembly module
with generated private state definitions. Migrate timer-1 register programming,
IRQ acknowledgement, enable composition and emulation vector ownership from
[sio.s](../../../platform/altirraos/sio.s). Preserve the existing fine-alarm
divisor and logical alarm units initially. Keep serial watchdog/queue/recovery
policy in its current owner.

Represent independent SIO-alarm and pointer-sampling demands. Acknowledge each
physical timer interrupt once and advance each eligible user at most once.
Centralize the timer bit in IRQEN/POKMSK composition so `sio_arm`, alarm expiry,
terminal/error, recovery and shutdown cannot clear a surviving pointer demand.
Service serial deadlines first and retain bounded serial rechecks around the
new work. Do not put a sampling Task or a new kernel selector between the ISR
and its fixed backends.

Handle both startup orders. The first compatible owner establishes a known
silent timing baseline and saves affected state once; subsequent owners preserve
it. Use authoritative write-register shadows, never reads from POKEY's unrelated
read aliases. Split restoration by affected resource: SIO shutdown cannot erase
timer-1 state while the pointer remains, and pointer shutdown cannot alter serial
clock channels or an armed alarm. Last-owner release restores owned vectors and
register state after pending activations retire.

Audit STIMER resets, pending IRQ latches and alarm arm/disarm races. A stale timer
edge cannot count toward a newly armed SIO alarm; acknowledge it without losing
the surviving pointer demand. Existing SIO transaction resets may shift the
sample phase, and that gap belongs in measurements. Pointer acquisition during
an active transfer must not reset the hardware clocks. Native routing and the
ROM's emulation vector must both service pointer demand when SIO is absent,
idle, terminal or offline.

Use a compile-time diagnostic fixed sampler to read the port and measure cost
before public pointer admission exists. Its overhead must be identified; M3
repeats the timing tests with the complete backend. Exercise either owner's
release, active alarm plus pointer stop, SIO-only operation, both active, last
release, incompatible pre-existing ownership, OS calls and NMI entry.

**Gate:** focused emitted SIO read/write phase, cancellation/recovery, watchdog
and alarm checks pass without changed deadlines. Trace no double acknowledgement
or double logical tick. Record the actual sampling gaps, including overruns.
Commit shared ownership and evidence before changing the input ABI.

## M2 Input ABI and source state

Change [input.json](../../../abi/input.json),
[input-native.json](../../../abi/input-native.json),
[tasks.json](../../../abi/tasks.json) and their generators. Regenerate Action!,
C and assembly definitions; retain compile-time C layout probes. Prepare source
descriptors, native capture placement and the POINTER producer entry, keeping
its admission unsupported until M3's backend is present.

Refactor [input.act](../../../lib/input/input.act) and its native/Task glue so
every operation resolves the correct descriptor. Migrate console, standalone
input fixtures and GEM keyboard clients to Config version 2. Update C packet
extent checks to 32 bytes. Preserve the existing keyboard's raw ring, cancellation
precedence and producer lifetime behavior.

Reserve explicit upper-memory extents before emitting code. The existing
generator bounds keyboard state/capture within Task-arena offsets `$0A60–$0E30`;
the new pointer arena must not simply be appended over native code at `$1000`.
Change generated placement and overlap checks as needed, recording complete
reservations and code movement. Preserve pointer-free builds as build selections,
not alternate public API profiles.

**Gate:** Action! and C emitted layout/value/extent checks in raw/optimized modes,
keyboard capture and console handoff checks, and producer-lifetime regressions.
Test old-version rejection, complete bank-boundary checks and mutation-free
unsupported pointer admission. Commit the ABI migration with rebuilt callers.

## M3 Native mouse capture

Implement ST decode, TRIG0 state capture and the raw stream in a bounded native
backend, connected to the M1 clock. Enable SOURCE_POINTER admission. The selected
protocol must not write PORTA, PIA controls or POTGO, and must not reset SKCTL.
Read PORTA once per sample for both axes; seed initial phases and require a
released button before generating an actionable press.

Implement the record, epoch and pending-output rules above. Impossible opposite
states latch HARDWARE loss; ring exhaustion latches RAW loss independently of
queue capacity. Disarm and rebase rather than guess direction. Preserve notices
for every affected retained route; do not overwrite a notice during recovery.
Later arrivals must survive notice acknowledgement.

Document every shared field's writer and guard. Task copies/coalescing updates
use bounded IRQ exclusion, with existing SWITCHING/context rules covering NMI.
Avoid a long IRQ-masked ring scan: skip/discard stale records in bounded chunks,
keeping Pending accurate. Use existing deferred wake publication, including
empty-to-pending transitions and wake retirement; no wake per unchanged timer
tick. Validate complete native and emulation register/stack restoration.

Run a standalone consumer with keyboard and pointer leases together, through
Action! and the C bridge. Cover source contention, copied/stale leases, distinct
acquisitions, route switch/zero/discard/retire, signal freeing while bound or
released-but-undrained, controller/recipient removal, acquisition rollback,
idle wake and repeated release/reacquire. Stop one source while the other and
SIO remain active. No private GEM code should be linked into this fixture.

**Gate:** emitted records agree with independent controller stimulus, all button
edges within the declared timing envelope survive, and failures produce bounded
loss/cleanup. Re-run M1 timing with actual decoding, queue publication and wakes.
Commit the reusable physical-input backend and its measured support envelope.

## M4 Interactive integration

Update [ui.c](../../../ports/gem4xe/interactive/ui.c) and
[ui-events.c](../../../ports/gem4xe/interactive/ui-events.c). Acquire a second
input lease/signal after keyboard admission, using ST/port 1 and 640×240 bounds.
Associate its full acquisition/route with the current GUI session. Validate that
association before translating to the private queue's keyboard/session identity;
do not merely rewrite an unvalidated event's tags.

Drain at most eight keyboard records and eight pointer events per turn, followed
by the existing bounded normalized/control drains and graphics completion check.
Include pointer data, loss and retained BUTTON output in Pending/Wait decisions.
Keep the existing one-packet renderer limit, fair cursor/redraw scheduling and
fenced background restoration.

Preserve the current press/matching-release behavior and disarm on loss, route
change or cancellation. Coalescing stops at button/identity/epoch barriers. When
mouse acquisition returns an ordinary error, unwind only its partial resources
and leave the keyboard scene usable; expose a bounded status. An absent mouse
cannot be reliably distinguished from a configured idle port and should not
prevent startup. Existing fatal/reset-required hardware ownership remains so.

Close GUI admission first, retire the mouse association and pending output,
release/drain its producer, then free its signal/lease before existing keyboard
and graphics teardown. Cover partial startup after signal, lease or route
allocation, close during motion/press, root stop, Escape/BREAK and late samples.
Do not allocate stop resources during shutdown.

**Gate:** controller-driven motion and clicks visibly operate each enabled
control during cold reads; release elsewhere/loss does not click; keyboard and
media-error paths still restore text and clear ownership. Commit integration
separately from the stress/measurement slice.

## M5 Coexistence and failure closure

Use the selected default machine/disk profile for ordinary development, with
targeted additional transport cases because shared IRQ ownership changed.
Reuse the existing SIO/keyboard/context observers; extend them to distinguish
physical timer edges, logical SIO alarms, actual PORTA reads, captured records
and visible cursor completion. Establish bounds before execution and do not
infer sample counts from acknowledged IRQs alone.

| Area | Required focused cases |
| --- | --- |
| Motion | Every Gray-code transition, both axes/signs, slow movement, reversals, diagonal motion, clipping and checked counter boundaries. |
| Loss | Opposite jumps, three/four hidden transitions, ring saturation, counter/epoch exhaustion, loss plus pending BUTTON, route reuse and recovery while held. |
| Timing | Idle and active SIO, command/payload/terminal transitions, timer reset/stale edges, VBI/DMA delay, OS calls and deliberately extended interrupt exclusion. |
| Ownership | Both admission orders, either release order, active/released binding holds, partial startup failures, shutdown/reacquisition and late IRQ/wake retirement. |
| SIO | Exact read/write data, armed alarm, cancellation before/during/after transport, NAK/absent media, timeout, offline/recovery and terminal retirement. |
| Interaction | Mouse plus typing, idle wake, continuous motion with redraws, press/release across a redraw, Escape/BREAK and exit while disk or graphics is pending. |
| Context | Raw/optimized Action! and C, native/emulation IRQ entries, NMI over publication/stack transitions, all registers and DP ownership, stack/domain guards. |

Require zero unreported count errors and no lost or duplicated supported button
edges inside the M0/M3 envelope. Exercise faster motion separately and report
aliasing limits; quadrature cannot expose every missed cycle. Measure maximum
capture gap, ISR cost, controller-to-capture delay and capture-to-visible delay.
Retain the design's initial 12-PAL-tick visible-response ceiling for the bounded
scene, for both keyboard and mouse during physical SIO. Report first outstanding
motion latency so coalescing cannot conceal starvation.

Check disk bytes and the existing SIO timing assertions, not only successful
request status. Include a targeted FASTEST125 case because the common ISR also
serves that profile; do not run the entire baud/placement matrix automatically.
If a fault-responder binary is needed, pin its mouse stimulus/observer additions
and distinguish it from the ordinary production binary.

Repeat the final workload with observers disabled. In the production link,
require real pointer capture and the session association to be present, while
diagnostic injection Tasks, test entry points and stimulus storage are absent.
The now-used pointer forwarding function is not itself proof of diagnostic code.

**Gate:** all selected cases pass within declared bounds, cleanup is exact, and
reports include both failures tried and final passing scope. Commit fixes with
the M5 evidence; development checks do not qualify all hardware/profiles.

## M6 Contracts and artifact

Publish implemented source/configuration, lifecycle, event and loss semantics in
the input/producer references, and update the platform's shared timer ownership.
Add ST/port 1 setup, host capture/release instructions and measured limits to
the GEM guide. State that Amiga, right/middle buttons, wheel, physical hardware,
NTSC, AES and desktop work are outside this milestone.

Build the optional demo through [build_demo.py](../../../tools/build_demo.py).
Keep OF816, the five-second standard-shell/prime autoboot, matching graphics
disk and pinned ROM. Ship only boot files, short guide, notices and checksums in
`exec816-demo.zip`; keep manifests, intermediates and reports under `build/`.
Use a screenshot from an executed production scene and record its provenance.

Test the packaged mouse scene with the documented Altirra map and wrong/missing
graphics disk. Run standard OF816 autoboot and Forth-to-shell controls, checking
keyboard, ordinary disk use and clean GEM exit. Verify ZIP whitelist/checksums
and license notices. Record production artifact hashes and memory/stack totals.

**Gate:** the packaged behavior, guide and fresh evidence agree. Mark M0–M6
complete only after those checks and commit the documentation/artifact work.

## Memory accounting and test scope

Each implementation record reports reserved bank-zero deltas, including guards,
alignment and unused capacity: target **fixed 0, root/kernel 0, each public Task
0 and private idle 0**. Keep eight public Task slots and the two 2,560-byte stacks.
Do not quietly grow a bank-zero vector stub reservation. A required increase
must first update the memory budget and this plan with its measured reason.

Budget 1,536 upper bytes for pointer capture, including its guards/slack, as in
the design. Separately budget and report shared timing state, enlarged source
metadata/config copies, the four-byte acquisition allocator, pending output,
UI lease/config/signal state and native/C code growth. Check whether each item
fits the allowance or existing owned capacity; count complete new reservations
and any whole-bank allocation. Do not double-count reused capacity as new free
memory. No additional VRAM is expected. M2 placement must cover every live phase.

Use the [development tier](../../contributing/testing.md): host suite for code
changes, affected generators with `--check`, and focused emitted-code cases.
Existing runners to extend/select include `test_input.py`,
`test_input_capture.py`, `test_producer_lifetime.py`, `test_sio_adapter.py`,
`test_sio_deadline_ticks.py`, `test_sio_recovery.py`, `test_gem_interactive.py`
and `test_gem_pointer.py` under `tools/`. Add dedicated mouse capture/timing
runners where these cannot express the new assertions; document their actual
CLI after implementation instead of assuming commands exist.

Every passing record includes compiler/ROM/emulator and source hashes, selected
cases, actual raw/optimized execution scope, bounds and maxima, clean-ownership
results, stack peaks, memory reservations, and observation/replay status.
Normalize host text newlines before parsing fixtures; preserve binary/ATASCII
bytes. Full qualification remains a separate release or explicitly requested
activity. Preparing this plan runs documentation content/link checks only and
changes all runtime memory reservations by zero bytes.
