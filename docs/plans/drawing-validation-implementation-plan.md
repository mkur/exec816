# Drawing validation and asynchronous scrolling implementation plan

[Implementation plans](README.md) · [Bitmap console plan](gem4xe/bitmap-console-implementation-plan.md) ·
[Display ownership](../reference/display.md) · [Platform protocol](../reference/platform.md)

Status: implementation started, 3 October 2026. This is performance step 2 after
[cheap idle input checking](console-idle-input-implementation-plan.md).
Validate display ownership once at each public drawing entry, then reuse that
validation through its synchronous internal work. Next, submit a complete scroll
as one copy-and-fill operation: one drawing owner, one hardware list in flight,
and input service while the blitter runs. Preserve argument validation, ordered
completion, fault recovery and the existing ownership contract.
Implement in executable slices D0–D6, committing each after its development checks.

The subsequent [whole-rectangle benchmark](../history/whole-rectangle-scroll-benchmark.md)
tests a synchronous combined copy/fill before implementing these slices. It
reduces isolated full-screen scrolling from about 122 ms to 29.6 ms, and repeated
scrolling from about 126 ms to 43–45 ms. It does not establish acceptable input
latency. D4–D6 adopt the combined operation with asynchronous completion and
measure responsiveness separately from scroll throughput.

## Execution record

- D0: [development evidence](../development/drawing-validation-d0.json) records
  the unchanged optimized image and its unobserved replay: thirteen pixel scenes,
  49 checks, 30 launches and 121.82/122.22 ms isolated scrolls. Native
  `DISPLAY.Check` spans account for 32.34/32.03 ms, including preemption. Public C
  entry counts avoid assumptions about shared return code. Host checks: 304 tests,
  four historical-source skips. Reserved bank-zero delta: fixed/root/kernel,
  each public Task and idle all **0 bytes**, including guards and capacity.
  Exact BUSY edges, isolated Task CPU and first-visible input timing remain
  unmeasured; the observer records elapsed bounds explicitly. Later acceptance
  must not substitute those bounds for the missing measurements.

## Baseline and intended gain

The [Q3 evidence](../development/console-idle-input-q3.json), recorded at
`24e05cd`, measures 121.82 and 122.22 ms for the two full-screen scroll scenes.
Input checking now costs 9.74 and 10.02 ms. The optimized XEX is
`c6796ebbf0400abb6120381eff86d3a5cdd8ad175c683908f9022c53fa4ec57c`.
Use that post-Q3 behavior as the comparison, with the pinned PAL ×8 65C816,
63 high banks plus base RAM, AltirraOS ROM and VBXE configuration.

The present drawing call structure still performs 49 `DisplayCheck` calls.
The first comparison keeps the current chunk sizes:

| Work in one scroll | Current ownership checks | Intended checks |
| --- | ---: | ---: |
| Fifteen `GemDrawingCopy` calls | 45 | 15 |
| One `GemDrawingFill` call | 4 | 1 |
| Total | 49 | 16 |

Each copy calls `GemDrawingFence`, which checks directly and through
`VbxeFence`, then calls the checked `VbxeCopyRect`. Fill checks at entry,
submits its list through checked `VbxeSubmit`, and calls the doubly checked
`GemDrawingFence`. Each display check reaches native `DISPLAY.Valid` and its
public `FindTask(NULL)` call. These are ordinary C/native library calls;
`FindTask` is the kernel gateway crossing inside them.

The earlier local trace at `build/bitmap-console/scroll-analysis/analysis.json`
measured roughly 36–37 ms in those 49 checks on the pre-Q3 image. That is a
historical indication, not a fresh measurement of this plan's baseline. D0 must
measure the post-Q3 image explicitly. Removing 33 checks suggests roughly
20–25 ms of savings if their cost stays similar; this is an estimate. The
separate 20 ms complete-scroll target remains open.

## Whole rectangle submission and responsiveness

The console currently copies at most sixteen pixel rows per worker turn. A
one-line scroll moves 232 rows, requiring fourteen 16-row copies, one 8-row copy
and one fill. This is a software responsiveness budget, not a required number
of public calls. Faster calls can move more rows before returning to input and
control service, amortizing validation, dispatch and continuation work further.

Two limits currently interact: the console's 16-row quantum and the driver's
8,192 estimated bus-access budget. A full-width copy uses 320 bytes per row for both source
and destination, so the driver allows twelve rows per launch. Each 16-row call
therefore becomes two launches: 29 copy launches plus one fill per scroll.

D0–D3 keep those limits fixed to measure validation savings independently.
D4–D6 use one submission containing two hardware commands: copy the retained
rectangle, then fill the exposed strip. Submission returns before hardware
completion. The existing console worker remains the sole drawing owner and
services input, control and queued requests while that list is in flight.

The design's [responsiveness targets](gem4xe/bitmap-console-design.md#worker-budgets-and-responsiveness)
remain 4 ms of CPU work per presentation turn and at most 40 ms from key capture
to visible output on the declared workloads. The initial 2 ms list-occupancy
target remains for ordinary synchronous lists. The proposed combined asynchronous
operation explicitly permits a longer list, bounded by its validated geometry
and hardware deadline. D6 must measure its occupancy and effect on pending
drawing; this exception does not establish a latency guarantee. Keep the public
arbitrary-list work limit unchanged. Hardware completion, input delivery and
visible echo are separate measurements: input can be processed during a scroll,
but its drawing must wait for the active list to finish.

## Validation boundary

A public operation means one ordinary `GemDrawingFill`, `GemDrawingText`,
`GemDrawingCopy` or `GemDrawingFence` call, or one direct public `Vbxe*` call.
A new call validates again, including the next console continuation. An entire
scroll, frame, VDI batch or acquired session is not one validation interval.
The new asynchronous start and completion-poll entries each validate once per
invocation. An in-flight record retains resources and operation identity; it
does not carry an admission grant across returns, Yield or Wait.

For an active, valid drawing operation, perform exactly one lease/Task identity
check before touching renderer state, flushing pending work or accessing hardware.
Reject an unauthorized caller without changing the actual owner's staging page,
queued records, fault latch, cursor state, mapping or VRAM. Existing argument-only
and terminal-fault early returns may reject without an ownership check where
they already do so without mutation. D0 freezes that status precedence.

Keep the responsibilities distinct:

- Existing public `Vbxe*` entries retain pointer-range and ownership admission,
  complete argument checks and synchronous completion. New asynchronous entries
  explicitly distinguish accepted, pending and completed work. Direct callers
  remain supported.
- Public GEM drawing entries retain ownership admission and their pixel/text
  argument contracts. They use private driver helpers within that invocation.
- Caller-supplied lists still validate every record before the first submission,
  including a bad later record. They never execute an accepted prefix on argument
  rejection. GEM-generated lists also retain the driver list validator: this
  plan removes duplicate ownership checks, not the hardware record boundary.
- Records constructed by the driver after validating a complete blit/copy can
  go directly to its existing private `submit` helper. Do not reinterpret those
  records through the public list API for every chunk.
- Pixel bounds, CPU buffer ranges, packed hardware fields, VRAM extents and work
  limits are different obligations. Retain each at its consuming boundary.
  Service packet/session validation remains unchanged.

Acquisition, activation, release and fault transitions keep their mandatory
`DISPLAY` checks. A close may need an admission check plus checked release
transitions; it is not subject to a one-`FindTask` lifecycle quota. A closed-session
idempotent close keeps its existing behavior. Pure geometry helpers such as
`VbxeBlitExtent` do not need a lease check.

## Internal implementation

Split `platform/altirraos/vbxe.c` into checked public wrappers and private helpers
that require an already validated owner. D1–D3 keep the ordinary public declarations
and record layouts unchanged. Expose only the helpers needed by the GEM adapter
through a private header such as `platform/altirraos/vbxe-internal.h`, outside
`c/include`. They are driver implementation, not a new public library contract,
Exec selector or driver-specific kernel operation.

The header must distinguish owner validation from argument validation. An
owner-validated submit still checks the whole incoming list; only the driver's
fully constructed records reach the existing unchecked `submit` leaf. Use names
and comments that make those preconditions explicit. Prefer static helpers when
no other translation unit needs them.

Apply the split to these paths:

| Current path | Refactoring responsibility |
| --- | --- |
| Read/Write → `transfer` → public Fence | Validate owner and CPU/VRAM extent once, then use a private fence/transfer path. |
| Palette → public Fence | Retain the 48-byte palette check and fence; reuse entry ownership. |
| Fill → public Blit → public Submit for each chunk | Validate the complete fill once; construct bounded records and use private submission. |
| Blit → public Submit for each chunk | Retain complete source/destination checks; submit constructed records without revalidation. |
| CopyRect → private `submit` | Preserve existing geometry/overlap logic; share its body with checked and owner-validated entries. |
| Show/Present/WaitFrame and Close composition | Reuse internal checked-owner work; preserve frame waits and lifecycle transitions. |
| GEM Copy/Fill/Text → public GEM Fence and driver wrappers | Admit once; flush/fence and draw through private helpers until return. |

Do not add a global “validated” bit, saved current-Task pointer, cached admission
token, new lock or per-Task cache. The proof is the synchronous call chain. The retained
lease keeps the owner alive; other Tasks fail the same public checks and cannot
release or steal it. IRQ/NMI handlers never enter drawing or mutate this lease.
Preemption can interrupt the owning Task, but only that Task resumes the private
operation. No new callback into arbitrary application code is allowed within it.
This follows the existing Exec resource model and
[mapping transition protocol](../reference/display.md#mapping-transition-protocol).
It is a shared-address-space contract, not protection against arbitrary memory writes.

Audit every caller of `drain`, `flush`, `vram_win`, blit and palette callbacks in
`ports/gem4xe/adapter/gem-vbxe.c`. They serve both the ordinary drawing library
and `GemVbxeBackend`. When they use owner-validated helpers, each service backend
entry that can reach them must also admit the owner before mutation. Command,
cursor, fence and close callbacks are separate invocations; do not retain a
validation grant between command and fence. Open must acquire successfully before
resetting renderer/cursor state. This is required caller migration, not cursor
optimization or a new service protocol. Test both `GEM_DRAWING_ONLY` and the
service-enabled build.

## Completion and failure rules

D0–D3 retain all existing fences and dependency ordering. Owner validation is
not a hardware-idle test. Keep fencing before CPU staging access, scratch/list
reuse, copy dependencies and release, and after each launched list. Preserve
the 16-row and 8,192-access driver chunk limits, 64-record limit, command arena
and mapping protocol through D3. D4 adds the explicitly asynchronous combined
operation below; existing synchronous APIs still complete before returning.

Private waits must keep unsigned tick deadlines and the existing recovery path.
If recovery releases a quiesced display, unwind the current operation immediately:
its entry validation no longer grants access. Do not launch another chunk, flush
a queued list, update presentation as successful or re-enter an owner-validated
helper after release. If hardware cannot stop, retain FAULTED ownership/storage
and park through the existing reset-required path. Mandatory recovery state
transitions are outside the normal-path check-count gate.

Preserve first-error latching and completed-prefix reporting. Keep prior-work
ordering for `GemDrawingCopy`: its existing fence can complete previously queued
work before the new copy's argument rejection. Tests must distinguish that work
from an invalid operation executing its own prefix. Empty calls still obey their
current owner/argument rules, including owner checking for a zero-count public
Submit; an empty operation is not a bypass for a foreign Task.

## One drawing owner and one operation in flight

Use the existing console worker as the sole owner of the drawing lease, command
arena and active operation. Other Tasks submit through the existing console
request queues; they never submit directly to this owner's blitter. This follows
Exec's driver-owned queue and active-request model. No semaphore or additional
rendering Task is needed for serialization, and no driver-specific kernel service
is introduced. Queued requests can outnumber active operations; at most one
hardware list may execute.

Use these states for the new shared drawing operation:

| State | Allowed work |
| --- | --- |
| Idle | Validate complete geometry and arguments, settle prior work, build and upload the copy/fill list, record its identity and deadline, then launch once. |
| In flight | Return pending promptly from a completion check while BUSY is set. Service input and control, but defer further hardware drawing and resource reuse. |
| Completed | Once idle is confirmed, publish one terminal result, resolve the console generation, finish presentation bookkeeping and permit the next launch. |
| Faulted | Follow bounded STOP/quiescence recovery; retain ownership and DMA storage if hardware cannot stop. |

A second start while busy returns a pending/busy result without changing the
active record or uploading commands. Start copies all needed descriptor fields;
it retains no pointer to a caller's stack packet. Keep the operation identity,
deadline, status and resource references in owner-controlled upper RAM. Keep
the single VRAM command arena and all source/destination storage alive and
unchanged by other drawing until completion. Restore MEMAC mapping before start
returns. A synchronous Fence or existing drawing call must resolve pending work
before dependent access; the console's asynchronous path must avoid invoking
those blocking calls while a list is active.

Initially detect completion with one bounded BUSY check per worker turn, only
while an operation is in flight. Keep VBXE IRQs disabled. Each pending turn
services input/control and yields fairly; pending hardware work keeps the worker
runnable, so it cannot enter an indefinite signal Wait with nobody to report
completion. There is no tight BUSY loop inside the asynchronous start or poll.
Use the existing wrap-safe elapsed deadline across turns; recovery may still
perform its bounded stop wait. Measure polling and Yield cost before considering
a timer or a separate IRQ producer.

Record completion durably before using the existing request reply/notification
path to wake a waiting client. Signals are coalescing wakeups, not result storage
or evidence that hardware finished. The polling owner needs no self-signal.
Preserve each existing request's byte-acceptance/completion contract; asynchronous
submission alone does not mark pixels synchronized or retract accepted bytes.

Commit the logical scroll once. Retain a protected operation association using
unit and generation, with an explicit lifetime hold where required; never keep
an unprotected instance/view pointer across a worker turn. Until completion,
defer further model writes to the scrolling instance and queue affected echo.
Continue input capture, read delivery where its contract permits, and bounded
work for other instances. For this first implementation defer all hardware
drawing, including unrelated tiles and the caret, while the list is active.

Cancellation, hide, retirement, shutdown and generation changes suppress future
drawing immediately, but cannot free active storage or undo pixels already
written. Observe completion or bounded recovery before releasing resources;
then invalidate the affected view or finish its current generation exactly once.
Late completion must never acknowledge or draw into a reused instance. Preserve
FAULTED ownership on unquiesced hardware and abort further private drawing after
any recovery release.

## Implementation slices

### D0 Record operation boundaries and baseline

Extend `tools/bitmap_console_performance.py` with native `DISPLAY.Check` and C
public-entry markers. Account for optimized C tail calls/shared epilogues when
choosing completion markers. Pair spans by Task DP as in Q3, attribute nested
checks to the outer operation, and keep nested timings separate.

Run the unchanged optimized scroll scenes and an observation-free replay.
Record ownership checks, `FindTask`, hardware launches/fences, driver records,
full scroll time and idle-input contribution. Confirm 49 checks, 29 copy launches
and one fill for each measured scroll. Add focused emitted call-count cases for
single/multiple chunks, copies, fill, text, empty operations and direct driver
calls. Record current errors and visible effects for rejected calls. Establish
per-call and complete-turn CPU time, excluding preemption, alongside elapsed
time, actual hardware BUSY intervals and gaps between input service. Extend
observation where necessary; launch-to-idle elapsed time alone is not hardware
occupancy, and existing fairness completion markers do not prove visible typing
within 40 ms.

Store proposed evidence at `docs/development/drawing-validation-d0.json`, with
full traces under `build/drawing-validation/`. Pin image, native/C compilers,
ROM, emulator and configuration. No production behavior changes in D0.

**Gate:** reproducible post-Q3 baseline and reliable ownership counts, with
matching pixels/statuses in the replay. Establish what is measured before
setting the final comparison.

### D1 Validate direct driver operations once

Refactor checked `Vbxe*` entries and their internal composition. Introduce the
private header, remove nested public Fence calls, and route driver-constructed
Blit/Fill records directly to `submit`. Keep public Submit's whole-list validator
and CopyRect's overlap, extent and descending-copy behavior.

Extend `tests/programs/gem_display.c` and `tests/programs/bitmap_copy.c` with
ownership/call-count cases where needed. Run focused raw/optimized emitted
checks through `tools/test_gem_display.py`: pattern, bitmap-copy, copy-fault,
map-nmi, busy/vcount/wrap timeouts and retained/unquiesced ownership as affected.
Reuse each compiled image across selected cases. Include production hardware-read
control for the successful copy path.

**Gate:** each valid direct operation has one admission check regardless of
chunk count, all public negative checks still reject, invalid lists execute no
prefix, and all touched recovery/mapping boundaries preserve guards and cleanup.
No GEM adapter caller uses the private interface yet.

### D2 Reuse admission within GEM drawing calls

Migrate the ordinary GEM drawing entries and every service callback that shares
their internal helpers. Replace nested public entry calls with private work after
admission. Keep independently callable public Fence and driver entries checked.
Preserve session output/status rules and stop work immediately after a latched
fault or recovery release.

Extend `tools/test_gem_drawing.py` or add a focused sibling fixture to exercise
two Tasks: one owns graphics with pending work, the other attempts drawing,
fencing and closing. Pause the owner immediately after admission and between
chunks, using existing fixture/NMI probes. The peer must fail through public
entries without altering pending commands, staging, state or pixels; the owner
then resumes and completes exactly once. No production critical section is added.

Cover these cases in emitted raw and optimized builds:

| Case | Required result |
| --- | --- |
| Copied, stale, released or foreign lease | Rejected before private hardware work; rightful owner remains usable. |
| Zero-sized operation from the wrong Task | Cannot bypass ownership admission. |
| Malformed later list record, VRAM wrap or command-arena overlap | No prefix from the invalid operation; complete range checks remain. |
| CPU buffer crossing a bank, touching MEMAC or crossing the address ceiling | Preserve valid carry handling and invalid-range rejection. |
| Invalid text/fill/copy after a clean fence | Preserve error/renderer state; no new pixels or queued work. |
| Preemption after validation or between chunks | Context and lease stay intact; peer attempts do not steal ownership. |
| Fault before launch or after a completed chunk | Correct prefix and one terminal result; no work after recovery releases the lease. |
| Unquiesced fault | FAULTED lease and retained storage; bounded reset-required park. |
| Close, reopen and a new owner | Fresh validation and initialization; no grant or queued work survives retirement. |

Run shared-drawing pixels plus selected service renderer and cursor regressions
through `tools/test_gem_render.py` and `tools/test_gem_cursor.py`. Exercise both
build forms; add a focused case selector if necessary rather than launching
unrelated release axes. Check the emitted symbol/call graph: private helper
callers must be accounted for, and public entry checks must remain present.

**Gate:** Copy, Fill, Text and Fence each validate ownership once on their normal
path, regardless of internal chunks/lists. No ownership, pixel, rejection,
service/cursor or recovery regression; all private entry paths have a checked
caller or a successful acquisition in the same invocation.

### D3 Validate integration and measure validation savings

Reuse the existing fixtures for development checks at unchanged chunk sizes:

- Thirteen exact-pixel bitmap scroll scenes with passive timing and an unchanged
  image replay through `tools/test_console_bitmap_scroll.py`.
- Continuation cancellation and all affected quiesced/reset-required failures
  through `tools/test_console_bitmap_control.py` and `tools/test_console_bitmap_fault.py`.
- Eight-Task physical SDFS/keyboard/BREAK and active ST capture through
  `tools/test_console_fairness.py --bitmap --pointer`, plus its unobserved replay.
  Keep the existing SIO, pointer and Forbid limits.
- A text-console ownership/handoff case, such as the existing G3 display launcher,
  to prove text startup remains mutually exclusive with graphics.
- Host checks and the raw/optimized cases from D1/D2. Repeat only checks affected
  by subsequent changes; do not run a full release matrix automatically.

**Performance gate:** on both matched optimized full-screen scroll scenes,
reduce normal-path `DisplayCheck` calls from 49 to **16**, reduce measured lease
validation time by at least **60%**, and reduce total scroll elapsed time by at
least **10%** relative to D0. Count any replacement admission work and caller
setup; moving a check beyond its old marker is not a reduction. Keep all 30
hardware launches, chunk limits, fences and the completed idle-input behavior.
A missed gate requires investigation and a recorded result, not silently claiming
the separate 20 ms target or including D4–D6 batching changes to satisfy this step.
Sixteen checks and thirty launches are comparison controls for D3, not final
performance requirements for the console.

Record proposed `docs/development/drawing-validation-d3.json` evidence, actual
call counts, timings, memory/stack usage and remaining cost. Update the current
[display reference](../reference/display.md),
[GEM adapter description](../../ports/gem4xe/adapter/README.md), bitmap plan and
roadmap only once the corresponding implementation is validated. Preserve Q3
and D0 as historical comparisons. Any optional demo refresh must use
`tools/build_demo.py` with OF816, matching media/ROM/notices and the five-second
standard autoboot. Publishing and release qualification are separate work.

### D4 Add asynchronous whole rectangle copy and fill

Define the shared drawing and driver start/poll/fence contract, including
accepted, pending, busy, terminal status and operation identity. Accept an aligned
rectangle copy and its exposed-strip fill colour; validate both operations
completely before launching either. Support full-screen and offset/narrow console
tiles, including a height-one tile that only needs filling. Keep the ordinary
copy API's overlap guarantees and reject unsupported combined geometry before
mutation. Do not expose unchecked hardware lists or remove arbitrary-list limits.

Split private launch from completion wait. Construct one ordered list containing
the copy and fill, upload it into the existing arena and return after launch.
Add the persistent active record and bounded completion poll described above.
Existing synchronous APIs compose these internal mechanisms where appropriate
while preserving their completion contracts. A new public poll is a new ownership
admission; the launch's validation does not survive its return.

Use focused raw/optimized emitted fixtures before migrating the console. Cover
exact pixels and neighbouring tiles, fill colour, argument rejection with no
prefix, a second submission while busy, foreign/stale ownership, preemption,
MEMAC restoration, descriptor-stack reuse and arena/source lifetime. Inject
timeouts before launch and during the combined list, tick wrap, successful
quiescence and unquiesced failure. Recheck direct synchronous calls, Fence, close
and reopen with an operation pending. No extra command arena is introduced.

**Gate:** start returns while a sufficiently long real list is still busy;
poll reports pending without spinning; completion is recorded once. A normal
scroll has one launch and two records, and no drawing or storage reuse can race
that launch. Existing synchronous APIs and recovery still pass. Record API,
memory and emitted evidence in proposed `docs/development/drawing-validation-d4.json`.

### D5 Service console input while drawing is in flight

Replace the row-copy continuation with one start and subsequent completion
checks. Keep the existing worker, request queues, input notification protocol,
source-byte quota and input-drain quota. Add pending drawing to runnable-work
detection and ensure the worker yields between pending turns. Audit Present,
caret, control and shutdown paths so they defer dependent drawing rather than
enter a synchronous fence during ordinary pending service.

Resolve unit/generation on each turn and maintain the required lifetime hold.
Finish copy/fill bookkeeping and caret redraw only after completion. Integrate
hide, cancellation, view retirement, worker stop and display release with the
active record. Preserve logical-scroll-once behavior and existing read/write
reply semantics, with exactly one terminal result per operation.

Run the thirteen pixel scenes and focused raw/optimized continuation, ownership,
cancellation and fault tests. Inject input and control while hardware is actually
busy; prove the worker services them before completion while deferring their
drawing. Cover generation reuse, queued requests, completion around a worker
turn boundary and an otherwise idle system where pending drawing is the only
reason to run. Repeat selected service/VDI regressions sharing the driver.

**Gate:** one owner and at most one active hardware list; input/control service
continues during it; no lost wake, busy-spin fence, premature reply, stale view
access or early release. Preserve guards, OS restoration and retained ownership
on failure. Record proposed `docs/development/drawing-validation-d5.json` evidence.

### D6 Measure asynchronous scrolling and input latency

Compare D3's synchronous chunks, the recorded synchronous whole-rectangle
experiment and D5's asynchronous path on matched pinned inputs. Measure isolated
and repeated full-screen scrolling, narrow tiles, and the shell/prime layout,
both idle and with physical SDFS and active ST capture. Include the declared
eight-Task stress workload and an otherwise idle pending worker.

Inject keyboard/BREAK and control near launch, during confirmed BUSY intervals,
near completion and across varying scheduling phases. Measure input service gaps,
capture-to-delivery and first correct scanout separately, cancellation delay,
Task CPU per turn, polling/Yield overhead, hardware occupancy and complete scroll
time. Account for time preempted; launch-to-idle observations are only an upper
bound on occupancy. Existing fixture presentation markers do not prove the
40 ms visible-input target. Replay the same images with observers disabled.

**Gate:** reduce complete scroll time relative to D3 with one submission and
one launch per eligible rectangle scroll, while meeting the 4 ms turn CPU and
40 ms visible-input targets on the declared workloads. Establish and document
the combined list's measured occupancy bound. Existing SIO, ST, BREAK,
cancellation and peer-service gates must pass. Report the separate 20 ms
complete-scroll target, including any remaining miss. Asynchronous return alone
does not satisfy these gates, and faster input delivery does not prove faster echo.

If the whole rectangle prevents latency acceptance, record the failing phase
and test a smaller bounded asynchronous rectangle before selecting production
geometry. Keep one operation in flight and preserve the input targets; do not
quietly restore blocking waits or claim the full-rectangle result for chunked
execution. Store the selected limits, counts and measurements in proposed
`docs/development/drawing-validation-d6.json`. Update current contracts and the
roadmap only for validated behavior, preserving historical evidence.

## Memory and scope

Expected reserved bank-zero delta is **0 bytes** for fixed storage, root/kernel,
every public Task and private idle. Count guards, alignment and unused capacity;
report actual deltas after each implementation slice. Keep the existing drawing
banks, 4 KiB staging and command buffers, MEMAC aperture and VRAM reservations.
Measure helper stack use and emitted C/native image changes in both modes rather
than enlarging a reservation preemptively.

Account for the D4 active record in upper RAM, including its full reserved
capacity and any lifetime hold. Reuse existing Task pools and request queues;
add no semaphore, second command arena or per-Task owner cache.

D1–D3 change internal validation only. D4–D6 add the shared asynchronous
copy/fill contract and console integration, with an explicit work-limit exception
for the validated combined operation. There is no new Exec gateway operation,
VBXE IRQ producer or broad Forbid/SEI region. Font rendering, cursor speed,
kernel scheduling and public INPUT validation remain separate work. Development
checks do not qualify the entire hosted system.
