# COP fast-path implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

The [refactor plan](../plans/kernel-fast-path-refactor-plan.md) keeps `COP #$50` and the
current public ABI. G1 records the unmodified runtime; G2/G3 implement native
exclusion and dequeue; G4 supplies integration evidence and a play image.

## Entry and completion contract

The common entry retains the full frame, activation-local signature decoding,
SWITCHING acquisition and stack/DP validation. A native service starts with X
pointing at the complete saved frame and Y identifying the service. It checks
the same service-specific width/tag/packet rules before mutation and publishes
the current saved stack fields as Dispatch did. Unhandled services continue
through `dispatch_frame` unchanged.

Fast handlers use stack-local scratch under SWITCHING. They restore S to the
saved frame and D to the gateway domain before either handoff. IRQ service is
allowed during the body when the caller entered with I clear; NMI never borrows
this scratch or schedules through the guard. The first version keeps the full
register save even though some services need fewer registers.

| State after a completed operation | Continuation |
| --- | --- |
| A tick, timer work or an IRQ wake is pending | Enter existing Poll dispatch with the original result frame. |
| Caller has pending rescheduling and is not protected by exclusion, I or OS activity | Enter Poll, including when the ready queue is empty, so pending bookkeeping retains its behavior. |
| No required work | Restore this Task through the existing guarded native return. |
| Invalid context, call shape, port or exclusion depth | Existing context-fault/OS-restoration path; do not modify the operation's target. |

The decision is made with IRQs masked. NMI can still set the tick hint; a tick
after the decision remains durable, as on the existing return path. IRQ wake
publication is excluded through the final decision and restore; general Poll
retains its final wake recheck. All scratch is retired before either route.
Forbid takes effect before Poll; Permit decrements once; GetMsg places its full
pointer result in the saved frame before Poll. Poll must not replay the service
or overwrite its result. No fast operation clears a signal, tick or wake hint.

Task-only queues retain public Forbid/Permit synchronization across a larger
driver transaction. A standalone GetMsg protects its own link writes only.
Native handlers are the single implementation of migrated services; their old
Action! mutation branches are removed. No caller chooses between implementations.

## G1 baseline

`tests/programs/kernel_fast_paths.act` executes 16 iterations of two nested
Forbid calls, three dequeues, and two Permit calls. Each iteration checks FIFO,
pending message type, empty result and both public nesting values. A second
scenario adds a ready peer, timed sleep, IRQ-compatible signal delivery and a
Wait that temporarily releases and then restores nested exclusion.

`tools/test_kernel_fast_paths.py` builds once per NIR mode and runs both scenarios
with identical-image untraced replays. Passive markers measure public imports
through their final RTL; times include any intervening scheduling/interrupts.
Reported CPU cycles are elapsed PAL ticks multiplied by eight, not an attribution
of all elapsed cycles to kernel execution. The minimum/median/max distinguish
the quiescent body from interrupted calls. Original artifacts remain under
`build/development/kernel-fast-path/g1-{raw,opt}`.

Both scenarios pass in raw/optimized code, with matching untraced replays,
81/87 assertions, intact guards and OS restoration. The host suite passes 197
tests. [Baseline evidence](../development/kernel-fast-path-baseline.json) records
the pins and exact image hashes. Median complete-call times on PAL 8x:

| Call | Raw | Optimized |
| --- | ---: | ---: |
| Forbid | 720.454 us | 683.979 us |
| Permit | 722.780 us | 686.305 us |
| GetMsg (empty and nonempty) | 842.815 us | 792.806 us |

All 144 measured coordination and submission calls enter the full dispatcher.
This is a development baseline, not a release or hardware qualification.

G1 adds no target reservation: **0 fixed and 0 per-Task bank-zero bytes**, including
guards, alignment and unused capacity. Its fixture data resides in upper RAM;
production code, stack/DP reservations, public ABI and compiler pin are unchanged.

## G2 native exclusion

`fast-services.s` handles Forbid/Permit after the common frame checks. All
accepted calls to these services use the native body; other selectors continue
to Action! dispatch. The old Action! Exclusion routine is removed. Completed
calls with deferred work enter Poll with their original saved result. During
the optimized 16-iteration measurement, 64 exclusion calls use the native body;
three require post-operation dispatch. Total full dispatches fall from 144 to 83.

| Call | Raw median | Optimized median |
| --- | ---: | ---: |
| Forbid | 46.132 us | 45.885 us |
| Permit | 46.978 us | 46.555 us |

The ordinary fixture and both untraced replays pass. A single assembly overlay
per NIR mode supplies nine runtime-selected native cases: register/flag/bank/DP
restoration, caller-masked restoration, bad tag, M/X widths, nonzero unused A,
foreign DP, unmatched Permit and depth overflow. The selected NMI fixtures
interrupt the private/public depth update and final decision, including I=1;
all 64 measured updates then complete through Poll exactly once. Forced WAI
latencies are excluded from performance claims.

Host checks pass 197 tests; Task/port generated definitions remain current.
The Task core and far-pointer fixtures pass in raw/optimized mode on their
original 1x profile, including real timer IRQs and OS restoration. See the
[exclusion evidence](../development/kernel-fast-path-exclusion.json).
Artifacts are under `build/development/kernel-fast-path/g2-*`.

The complete raw/optimized memory maps match G1: **0 fixed and 0 per-Task added
bank-zero bytes**. Native code uses 6,747 of the existing 8,704 upper-RAM code
bytes, up from 6,479 in this fixture. The handler adds ten activation-local
bytes below the 13-byte COP frame within the existing 256-byte interrupt reserve;
it retains no extra call frame. Guards, alignment and all reserved capacities
are unchanged. No public ABI or compiler pin changes.

## G3 native dequeue

GetMsg now validates and removes the head under the same native guard. Its
Action! service branch is removed; general Lists routines still serve their
other callers. Packet bounds, port tags/actions, full 24-bit pointer results,
empty sentinels, stale removed links, message types and signals retain their
contracts. Results survive post-operation Poll without a second dequeue.

Median complete calls in the raw/optimized coordination fixture:

| Call | Raw | Optimized |
| --- | ---: | ---: |
| Forbid | 47.577 us | 47.506 us |
| Permit | 47.647 us | 47.894 us |
| GetMsg | 77.110 us | 77.004 us |

All 112 measured exclusion/dequeue calls use native bodies, with two requiring
post-operation Poll. Including 32 ordinary PutMsg calls, full dispatches fall
from G1's 144 to 34. These figures exclude forced interrupt-stall fixtures.

Development coverage includes raw/optimized FIFO, context/masked calls, bank
crossings, immediate reply reuse and signal-before-Wait. Ten additional invalid
GetMsg scenarios per mode reuse the native overlay: null/overflowing port,
wrong type/action, out-of-bounds argument packets, wrong tag, width and unused
A bits. They fault before altering queue links. NMI checkpoints cover arrival
after the last fast-return decision and after a completed dequeue result.

The dequeue race hook now interrupts the native operation between its two link
updates. A preserving assembly wrapper permits real serial IRQ posting and NMI
while the wake recipient remains excluded. The older shared race harness also
needed its stale signal-post prologue assumption updated to preserve binding
selection. The harness keeps its existing enqueue/reply and ownership checks;
none of those checks is removed. Test-only stack use is recorded separately.

The focused Task/port runners accept an explicit pinned `--profile 8x`; their
1x defaults remain available. The far Task fixture now performs Forbid/Permit
from the Task whose public record crosses a bank boundary, checking its mirror.
All 16 selected port cases, both far Task cases, 38 native context/fault cases,
and eight coordination/NMI scenarios with eight identical-image replays pass.
The host suite passes 197 tests; Task, port and SIO-adapter generator checks
pass. [Dequeue evidence](../development/kernel-fast-path-dequeue.json) records the
scope and pins; artifacts remain under `build/development/kernel-fast-path/g3-*`.

Native code uses 7,038 bytes in the small fixture. To accommodate the same code
with the resident console, the native subregion grows from 8,704 to 9,216 bytes
inside the already reserved upper Task arena. The complete memory maps still
match G1. Reserved bank-zero delta remains **0 fixed, 0 per Task**, counting all
guards/alignment/capacity. Scratch is now 20 bytes below the saved COP frame,
within existing interrupt headroom; no stack, DP or full arena grows.

## G4 integration and play image

All four slices are complete. The [integration evidence](../development/kernel-fast-path-integration.json)
records hashes, timings, replay comparisons and validation scope. Production
runtime sources are G3 (`82010c7`); G4 adds measurement/reporting and refreshes
the bundle. The compiler pin and public ABI remain unchanged.

### Complete public calls and combined sequence

Reanalysis of the retained G1/G3 traces avoids another compiler build or emulator
run. Optimized median elapsed CPU cycles fall from about 9,704 to 674 for Forbid,
9,737 to 680 for Permit, and 11,248 to 1,093 for GetMsg. These are PAL base ticks
times eight, including the import's final RTL and any interrupt/scheduling time;
they are not exclusive instruction counts. The evidence retains minimum,
median and maximum values in both modes.

The larger sequence includes **two Forbid calls, three GetMsg calls, publication
and clearing of the active pointer, two Permit calls, and fixture assertions**.
Its 16-sample median falls from 5.581 to 0.566 ms in raw code and from 5.237 to
0.558 ms in optimized code (89.3% lower). The optimized measured interval has
112 native completions, two post-operation Poll entries and 34 full dispatches,
including 32 ordinary PutMsg calls; G1 had 144 full dispatches.

Every one of the 112 raw and 112 optimized native completion observations has
S exactly 33 bytes below public-import entry and local D equal to S: the 13-byte
COP frame plus 20 bytes of scratch. This is the native body's stack maximum,
excluding asynchronous nesting and general Poll. Existing stack/domain guards
and restoration checks pass; this is not a whole-system worst-case stack claim.

### Serial coexistence with ready peers

The four-Task `ports` workload sends 4,096 bytes while exercising message bursts,
exclusion, dequeue, reply reuse, registry operations, heap activity, Yield and
Sleep. Raw and optimized runs pass their identical-image uninstrumented replay,
with identical progress counters, exact ownership restoration and no leaks.
The target is 125 kbaud; the pinned clock produces 126,674.8 baud and a 78.942-us
refill deadline.

| Observed interval | Raw | Optimized |
| --- | ---: | ---: |
| Late refills | 0 / 4,095 | 0 / 4,095 |
| Longest ready-to-refill | 67.665 us | 60.898 us |
| Longest I=1 interval during transfer | 68.299 us | 71.400 us |
| Completion post to worker resumption | 3.087 ms | 5.702 ms |

During transfer, raw/optimized code completes 74/88 native services, with 7/9
post-operation Poll entries. Full Action! dispatch entries total 149/163 across
all services. These counters describe different progress in a fixed transfer
window, not identical amounts of foreground work.

The optimized complete-call elapsed ranges are 47.154–74.431 us for Forbid,
82.466 us–6.862 ms for GetMsg, and 2.353–17.683 ms for Permit. Outermost Permit
may reschedule; a suspended caller's elapsed latency includes other Tasks.
The parser pairs calls by native stack and excludes calls crossing either
measurement boundary. The evidence records counts, means and p99 separately
from the quiescent medians. This is diagnostic TX coexistence, not production
SIO/RX or real-hardware qualification.

### Same-profile cold HELLO

Compared with the [completion-collection baseline](../experiments/sio-completion-collection.md),
ROM, emulator, compiler, media, HELLO payload, instrumentation and timing settings
match: PAL 8x, GENERIC57600, 720 × 128-byte SDFS, accurate disk rotation, no burst
I/O or SIO patch. HELLO remains 2,359 bytes, with 19 data sectors in one Read.
Each observed run matches its identical-image untraced replay in relative phase
ticks, transfer counts and all 18 hardware inter-sector gaps.

| Interval | Stopped: before → after | Active: before → after |
| --- | ---: | ---: |
| Mean reply retirement/collection | 3.795 → 3.206 ms | 4.198 → 3.760 ms |
| Mean inter-sector gap | 16.799 → 16.869 ms | 18.566 → 20.208 ms |
| Largest inter-sector gap | 18.481 → 18.519 ms | 25.819 → 37.102 ms |
| Payload phase | 2.46 → 2.50 s | 2.42 → 2.48 s |
| Open to prompt | 4.10 → 3.90 s | 4.14 → 4.14 s |

Reply collection improves, but payload and sector-gap timings do not. A further
passive trace of the unchanged active image adds scheduler return markers and
reproduces the same phase and gap times. The longest gap, after sector 76,
contains SIO and filesystem resumptions interleaved with other Task pools; no
native fast service completes in that gap. Its 13.829-ms consume interval itself
contains other Task resumptions. These are elapsed scheduling intervals, not
exclusive copy costs. Rotation and changed scheduling phase prevent a uniform
end-to-end speedup. The private SIO control protocol remains for the separate
driver migration; these results establish its new baseline.

### Packaged result and memory

`build/demo` contains the refreshed play bundle. The previous complete bundle
is retained at `build/development/kernel-fast-path/previous-play`. The loading
smoke passes HELLO, `CAT STORY.TXT | WC`, MEM, physical BREAK during command
loading, another HELLO and MEM, with heap/ownership recovery and a peak of seven
Tasks. The host suite passes 199 tests, including two timing-parser regressions.
G2/G3 supply the focused raw/optimized interrupt, context, fault and port checks;
no full release matrix or compiler qualification was run.

The play, diagnostic and prior bundles have identical complete memory and Task
reservations. G4's reserved bank-zero delta is **0 fixed bytes, 0 per Task**,
including guards, alignment and unused capacity. The demo uses 8,859 of 9,216
native code bytes in the existing upper Task arena. Production scratch remains
20 bytes within the existing 256-byte interrupt reserve; the preserving dequeue
race probe adds 20 test-only stack bytes. No Task stack, DP or full arena grows.

Build manifests identify `82010c7-dirty`, reflecting G4 harness/documentation
edits present during packaging. Exact play and diagnostic hashes are in the
evidence; their production runtime is the committed G3 implementation.
