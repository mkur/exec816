# SDX resident page-one stack

Status: implemented with the latency target open, 2026-10-24. The
[current runtime contract](../reference/sdx-runtime.md) and
[development record](../history/sdx-resident-stack.md) describe the delivered
single-guest bridge. The copying bridge below describes the starting point.

Keep one active emulation-mode guest's stack in physical `$0100–$01FF`, including
while its native adapter waits. Native Tasks keep their existing private stacks.
Adapt ROM entry to borrow unused space below the guest's live frames, removing
whole-page stack saves and restores. A persistent FastBasic interpreter may park
between runs, keeping its Process, private memory and BASIC state while releasing
page one for EDX, ARC, MD5 or a compiler invocation.

This follows the user's selected policy: **one active guest, with idle BASIC
parking**. It deliberately replaces concurrent guest execution, while retaining
native Task preemption. ROM stack headroom and asynchronous entry must be proved
before the new runtime replaces the current bridge.

The [RS0–RS7 implementation plan](sdx-resident-stack-implementation-plan.md)
orders the bounds, lifecycle preparation, coordinated cutover, integration,
RAWCON work and delivery.

## Motivation and measured baseline

The native scheduler saves registers and S; it does not copy native Task stacks.
The copying belonged to the previous emulation bridge. In the starting version of
[sdx-runtime-probe.s](../../platform/altirraos/sdx-runtime-probe.s), every ordinary
guest-to-native service transition saved 256 guest bytes and restored 256 host
bytes. Resuming saved 256 host bytes and restored 256 guest bytes: **1,024 copied
payload bytes per complete service round trip**, excluding register frames.

EDX makes many RAWCON calls per key. The unchanged packaged binary produced this
[development baseline](../history/edx-interaction-baseline.json):

| Interaction | Key offer to next input-ready checkpoint | RAWCON cell calls | Flush rows |
| --- | ---: | ---: | ---: |
| End of line | 160 ms | 10 | 2 |
| Insert character, two samples | 321 ms each | 74 each | 2 each |
| Cursor down | 221 ms | 18 | 3 |
| Cursor up | 201 ms | 13 | 3 |

These are five samples on the pinned PAL, 8× 65816, VBXE desktop, with physical
key-matrix input and native-entry snapshot replay. Completion observes input
readiness and cleared console damage at an NMI checkpoint. It is a frame-quantized
upper bound that includes a three-frame key hold, not an independent measurement
of visible scanout. The record pins the ROM, emulator, optimized compiler and
package hashes; it does not qualify boot or the proposed runtime.

Insertion's measured editing phase was 201–214 ms and its screen flush took
63–64 ms. These include dispatch, guest execution and preemption. The four copy
loops were not timed separately, so removing them cannot be credited with the
whole editing phase. Full-row console requests are another material cost.

## Execution and ownership contract

Keep `E=1`, `M=X=1`, guest PBR/DBR and the private aligned direct page. The
[W65C816S stack rules](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf)
fix emulation S to page one; they do not require copying it. Moving the guest to
native mode would also change direct-page wrapping and require another binary
audit. That is outside this refactor.

Separate two resources that the current `slots=2` definition conflates:

| Resource | Proposed capacity and lifetime |
| --- | --- |
| Loaded guest Image/private DP slot | Two, retained until normal Image release. |
| Active page-one execution lease | One, shared by SDX and FastBasic. |
| Persistent BASIC Process | Retains its Task, Image, private DP/bank and native resources while parked. |

A second activation fails promptly with primary result 20 and native
`IoErr=202` (`ERROR_OBJECT_IN_USE`). There is no queue and no implicit reset or
termination of the existing guest. The native Process launch may already have
succeeded; the guest runner reports this execution failure through its ordinary
completion result. BASIC reports the failed Run without losing retained state.

An ordinary guest keeps the lease across native service calls, input waits,
device waits, preemption and cancellation cleanup. BASIC `INPUT`, `PAUSE` and a
future debugger stop during a live invocation also retain it. Backgrounding a
Process does not make its guest stack disposable. EDX waiting for a key therefore
prevents another guest from executing; other native Tasks continue to run.

This uses ordinary Exec Process, message, signal and resource ownership rules.
The single active context is a platform restriction imposed by the emulation
stack, not a new Task class or scheduler policy. No driver-specific private
kernel service is introduced.

## Image loading and lease lifetime

Retain load-time allocation of one of the two private DP slots and its upper
guest bank. Split `SDXSTATE.Prepare` into private-memory initialization and
execution-frame construction: loading another Image must never write physical
page one. Apply the same split to FastBasic initialization and reset.

Acquire the execution lease in the guest runner before constructing any physical
frame, changing console mode or starting guest-visible I/O. An unsuccessful
acquisition leaves the existing guest and retained BASIC data untouched. This
does not require a new public Process admission operation.

The lease names the owning Session and Task lifetime. It remains published while
an interrupt adapter, native service, trap or overlay can reference its frame.
Release follows complete retirement of those activations and outstanding I/O;
normal Image/Process attachment and collection prevent freeing the descriptor
early. Cancellation and failed startup use the same retirement path. An ARC
overlay remains part of the existing owner, rather than acquiring a second lease.

Reusing a loaded Image creates a fresh invocation stack after acquiring the
lease. No page-one pointer may escape its owning invocation. Startup's old ROM,
loader and monitor activations must have retired before the first lease can be
granted; arbitrary historical page-one contents are not a preservation contract.

## Resident frames and transition protocol

Keep an upper-memory execution descriptor in the existing resident bank. It
records the owner, private DP/bank, saved native S/D, complete guest-frame S,
event and transition phase. Keep the lifetime lease distinct from the current
CPU mode: a native service or another native Task can run while the lease remains
owned. The current `SR_OWNER=0` meaning cannot simply be retained unchanged.
An owned lease does not identify the interrupted CPU context as guest code;
classify entry using the captured bank, mode and transition phase.

| Phase | Page-one rule |
| --- | --- |
| Free or BASIC parked | No resumable guest frames; normal controlled ROM stack entry is allowed. |
| Entering | Lease acquired; construct the initial frame under the entry gate. |
| Guest running | Hardware S is authoritative; a previously saved S may be stale. |
| Native service/wait | Complete guest frame stays resident; its saved S is the ROM borrow anchor. |
| ROM activation | ROM uses the anchor or a nested activation's current S; guest resume and lease changes are excluded. |
| Restoring | Complete-frame return protocol owns the partially restored registers and stack. |
| Retiring | Discard resumability, settle references, then release the lease. |

On guest entry to a service or interrupt, save the complete context and select
the native stack before allowing native dispatch. Publish a borrow anchor only
after the complete guest frame exists. On return, exclude new ROM borrowing
until the guest's restored S and return frame are coherent. Preserve hidden B,
X/Y, P, D, DBR, PBR/PC and the complete native caller context.

Short transition gates combine local IRQ masking with the existing documented
NMI acknowledgement/defer protocol. `SEI` alone is insufficient. An NMI during
entry or a partial return must identify the phase, latch pending VBI work and
reach a complete-frame checkpoint before ROM work or scheduling. A guest-running
interrupt captures the current S; it cannot borrow from a cached service S.
Native peers may be scheduled after ROM activation retires, leaving the guest
frame resident throughout their execution.

Publish transition phases with an atomic byte store before changing S or any
multi-byte owner/frame field. NMI entry must inspect that phase before consuming
those fields; publish the stable anchor only after its frame and descriptor are
complete. Keep the old descriptor alive until all entry paths have retired.
Acquisition, frame relocation and release use this same protocol. Do not wait,
allocate or call DOS while a transition is incomplete; ordinary native service
waits happen only in the stable native-service phase.

Preserve the early emulation IRQ/NMI intercepts, bank classification and ROM
shadow preimage/restoration checks. Their role in reconstructing PBR and fixing
DBR survives removal of copying. Preserve prompt raw serial/pointer IRQ handling;
remove copy-loop polling only with the loops themselves. Do not defer interrupts
for an entire editor operation or guest invocation.

`SDXSTATE.GetFrame` will address the saved physical frame using its S and the
generated field offsets, rather than addressing an upper-memory page snapshot.
Update SDX printing, files, traps, overlays and every FastBasic frame consumer
together. Trap delivery may still move its bounded 13-byte frame for a nonlocal
unwind, with the same transition/ROM exclusion. Register saves and these small
frame moves are distinct from whole-page context copies.

## ROM stack borrowing

Single-guest admission alone is insufficient. The current
[hosted adapter](../../platform/altirraos/hosted.s) selects
`OS_STACK_TOP=$01EF` when entering ROM from an ordinary native stack. That would
overwrite the suspended guest's live stack.

Centralize OS stack selection for runtime ROM calls, VBI/IRQ forwarding and
runtime diagnostic entry. Classify boot, final return and test-only stack-reset
sites separately. For the pinned AltirraOS 65816 ROM, both native COP `$00`
services and the native VBI path enter emulation internally; a native Task stack
cannot simply be passed through unchanged.

When a guest has a complete resident frame, its saved S identifies the free
byte below that frame. Start the ROM borrow at that S or lower, so pushes grow
away from live guest bytes. Include the borrow wrapper's saved native S and
synthetic interrupt/service frames in its stack cost. Restore the interrupted
native S when the activation finishes; the guest's saved S and live frames
remain unchanged. If already executing on page one, preserve that activation's
current S for nested entry, rather than resetting to the guest anchor.

With no guest lease, use the controlled ordinary OS stack top. While ROM is
active, preserve `OS_BUSY`/interrupt-depth exclusions: do not acquire, park,
release or resume a guest, and do not schedule across a live ROM activation.
Service deferred VBI work at a safe complete-frame boundary before guest resume.
Preserve native SIO ownership and its restriction on ROM serial entry.

Borrowed dead stack bytes may change. Replace tests that require equality of
all 256 host/page bytes with exact live-frame, saved-register and guard checks.
Audit admitted binaries for absolute page-one storage or pointers outside their
live stack; such bytes cannot silently become ROM scratch. Keep the existing
restriction on guest stack pointers passed to native services.

### Headroom is an implementation gate

Do not assign an arbitrary half-page to ROM. Keep the existing lower guard at
`$0100–$010F`. If `Sg` is the complete saved guest S and `R` is the proven maximum
additional downward consumption, require:

```text
Sg - R >= $0110
```

`R` includes wrapper saves, synthetic frames, ROM's native-to-emulation paths and
the permitted IRQ/NMI nesting. Separately bound guest execution and the immediate
hardware/entry pushes that happen before software can inspect S. A boundary check
after a wrapped stack has overwritten live data is too late.

Audit the pinned ROM listing and emitted adapter paths, then corroborate the
bounds with nested-entry and deep-stack probes. Existing SDX/ARC watermarks and
the current minimum-S constant do not prove combined ROM/guest headroom. Preserve
the pin and configuration in each executable record; another ROM needs its own
audit. Guard failures must reach the native fault path before unsafe borrowing.
If an admitted binary cannot satisfy the bound, revise the entry paths or its
documented admission before replacing the runtime. Stack copying and long NMI
masking are not fallback modes in the resulting implementation.

## Parking the persistent interpreter

The [existing persistent-session design](fastbasic-session-plan.md) retains
variables, arrays, strings, modes, RNG state and open channels. Its native
Process waits for Run/Reset/Quit messages between invocations. A subsequent
invocation already constructs a fresh guest stack; this is the parking boundary.

At END, Stop or an invocation-ending recoverable error, finish output, native
requests, console restoration and diagnostics. Retire all resumable guest frames,
traps and overlay obligations, then release the lease. Publish the completed
result and reply only after the Process is parked and page one is available.
Retain its private DP/bank, symbol/data arenas, native handles, ports and Process.
There must be no pending native operation referring to page-one scratch.

The next Run first reacquires the lease, then constructs a fresh physical frame
against the existing private state. A busy result does not begin parsing, reset
symbols or alter BASIC values. Check/Build and EDX/ARC/MD5 can execute while the
interpreter is parked, subject to the two retained Image slots and normal Task
capacity. Their completion makes a later Run possible; no interpreter reload is
required.

Initial attachment initializes private state and replies ready while parked.
Restart interpreter clears its private state and resources while staying parked;
defer physical frame creation until Run. Quit also retires native resources
without touching another owner's page one. Numeric-mode switching keeps the
existing engine-replacement semantics. This boundary does not permit parking a
live BASIC wait, arbitrary guest continuation or debugger pause.

## RAWCON and console refresh

Measure the stack change independently before changing rendering. Then use the
resident-frame bridge for short nonblocking RAWCON cell read/write operations.
A bounded native leaf path may avoid the general yielding dispatcher for those
operations, while retaining domain guards, register restoration, cancellation
checkpoints and the same error delivery. Blocking keys, DOS I/O and console
requests stay outside the transition gate. Clear/scroll loops must preserve
bounded interrupt and cancellation service, including at maximum geometry.

Keep EDX's application-owned ATASCII buffer, software inverse caret, readback
and fixed invocation geometry. Replace dirty-row flags with first/end changed
columns per row, following the console's retained damage model. Ignore writes of
the existing value; clear and scroll mark their affected spans. A row span can
include unchanged gaps between two changes, so a distant caret move may still
produce a wide span.

Flush each dirty span through the public synchronous
`DOS.ConsoleIO(WRITE_CELLS)` column/row offset and count. Preserve FIFO ordering
and flush-before-key behavior. Clear a span only after its full write succeeds;
retain causal errors and restore cooked mode on retirement. Do not reach into
console-driver buffers, bypass ownership or add a private kernel operation.
Unchanged editor status/caret cells must not create damage. Empty input waits
must not cause redraws. Physical presentation remains the console's responsibility.

Use the pinned 64×20 desktop for a proposed development target of p95 ≤100 ms
for ordinary insertion and caret movement, with at least 20 samples per operation.
Measure input-ready latency and independent key-to-visible-scanout latency
separately. Record stack-only, span and leaf-dispatch effects separately; scrolling
and large-document operations need their own bounded workloads. This is a target,
not a prediction supported by the five baseline samples.

## Memory and generated contracts

The proposed **reserved bank-zero delta is zero**: 0 fixed, 0 root/kernel,
0 per each of the twelve public Tasks and 0 idle bytes, including guards,
alignment and unused capacity. Native stack/DP pools do not grow.

Keep the existing 544-byte fixed SDX DP reservation: two aligned 256-byte private
pages and two 16-byte outer guards. Parking needs both private pages; limiting
active execution to one does not free either reservation. Page one and its lower
guard remain inside the existing OS reservation. New descriptor/phase fields use
the already reserved 64 KiB upper bridge bank. Removing upper host/guest page
images reduces live use within that bank, not its reserved size.

The row-span arrays replace 30 dirty bytes with 60 bytes, adding 30 upper-heap
bytes per SDX Session before layout/alignment. Report actual Session allocation,
heap rounding and code extents in implementation records. Private guest-bank
allocations and retained interpreter storage remain; no parked-stack snapshot is
added. Any implementation requiring more bank-zero space must revise this budget
explicitly before proceeding.

Change [abi/sdx.json](../../abi/sdx.json) and
[generate_sdx.py](../../tools/generate_sdx.py) to distinguish retained Image slots
from active contexts and describe the resident descriptor/frame contract. Generate
bindings and reference outputs, and rebuild every consumer together. Remove the
obsolete page-copy layout and dual-execution branches from the resulting tree;
do not keep compatibility profiles. Guest file formats need not change solely
because internal frame storage changes. Exec still uses COP `$50`; ROM retains
its COP `$00` service and native ABI.

## Validation and migration

Implement in executable slices: freeze the baseline and stack bounds; introduce
the single lease, resident frames and ROM borrowing; add BASIC parking; then
measure RAWCON dispatch and spans. Keep the current runtime until the stack and
interrupt gates pass. A separate implementation plan should define commit-sized
work and exact test commands.

Development acceptance must cover:

- Two loaded Images with exactly one active lease; deterministic busy results
  without mutation; owner cleanup, failed entry, cancel and Image reuse. A native
  peer must continue running while an input-blocked guest retains the lease.
- Physical live-frame preservation across services, preemption and ROM calls
  made by a different native Task. Verify unchanged guest registers and DP,
  exact trap/overlay returns, guards and absence of whole-page copy operations.
- Forced NMI at each entry/return/publication boundary, including partial pops
  and nested bank-zero stubs; deep guest/ROM stacks at the admitted bounds;
  prompt serial and port-2 pointer IRQs with actual device activity. Prove fault
  entry before unsafe borrowing, rather than relying only on canaries.
- Persistent integer/FP BASIC state across Run → parked EDX/Check/Build → Run,
  including arrays, strings, channels, RNG, Stop and recoverable errors. Busy Run
  preserves state; Restart/Quit while another guest runs never touches its stack.
  Live BASIC waits continue to exclude another guest.
- EDX typing, caret, status, horizontal/vertical scroll, save and BREAK cleanup;
  ARC no-argument help and overlays/mutation; MD5 verification. Preserve exact
  ATASCII behavior, error causes and console ownership while measuring latency.

Use optimized emitted code for system scenarios. Add focused raw/optimized
frame-layout and language-boundary probes where the internal ABI changes.
Replace two-active-guest expectations with the new explicit admission contract;
preserve historical qualification records and their scope. Targeted deeper
interrupt/transport checks are necessary; development results alone do not
qualify the hosted system.

After implementation, update current reference contracts and refresh the demo
through `tools/build_demo.py`, including OF816 and its five-second standard
autoboot. Verify the preferred combined D1 SYS/WORK image for ATR, XEX and cart
launch, bundled SDX tools and separate QED ATR. This design-note change performs
content/link checks only and changes no executable or reservation.
