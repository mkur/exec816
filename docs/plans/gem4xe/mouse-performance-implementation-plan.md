# Mouse sampling and pointer batching implementation plan

[GEM plans](README.md) · [Desktop plan](desktop-implementation-plan.md) ·
[Input contract](../../reference/input.md) · [Display contract](../../reference/display.md)

Status: MP1–MP2 implemented at the development tier, 2026-10-05;
[evidence and limits](../../history/mouse-performance.md). MP3–MP4 remain planned.
The remaining text preserves the implementation plan. Reduce normal ST mouse sampling from about 8 kHz to
4 kHz and submit a complete pointer move as one bounded VBXE blitter list.
Keep the desktop's current two pixels per decoded step. Implement MP1–MP4 in
order, committing each executable slice with its focused development evidence.

This follows the working DT0–DT7 desktop and the sensitivity change in
`fbce56f`. One presentation Task continues to own the display. Input queues,
registration lifetime, asynchronous scrolling and window policy keep their
existing contracts. No new Task, kernel operation, pointer protocol,
acceleration curve or asynchronous cursor request is needed.

## Starting evidence and expected benefit

The [shared timer configuration](../../../abi/platform-timer.json) currently
sets AUDF1 to 7. On the pinned PAL machine:

| Setting | Physical Timer 1 rate | Nominal period |
| --- | ---: | ---: |
| Current, AUDF1 = 7 | 7,917.18 Hz | 126.308 µs |
| Proposed normal rate, AUDF1 = 15 | 3,958.59 Hz | 252.615 µs |

These follow `1,773,447.5 / (28 * (AUDF1 + 1))`. “4 kHz” denotes the second
setting, rather than exactly 4,000 Hz. Change the physical timer frequency;
skipping alternate samples while always taking 8 kHz interrupts would retain
most of the entry/routing cost.

The latest boundary check of the current 2× build recorded 29,628 samples,
29,628 physical timer edges and 29,628 dispatches. Its mean sample gap was
126.308 µs, maximum 166.554 µs. Native IRQ entry through routing averaged
39.745 µs; the sampler itself averaged 7.086 µs. That IRQ interval excludes
scheduler/RTI and can include other routed work. It is not a measurement of
exclusive mouse CPU use. The local result is
`build/desktop/pointer-scale-opt/rate-check/results.json`.

The [DT6 two-client measurements](../../history/desktop.md#dt6-shutdown-failures-and-two-client-load)
record roughly 31–36% of elapsed time inside native IRQ entry through routing.
Pointer capture was accurate, but presentation latency remained high. Reducing
interrupt frequency should release CPU time; batching should separately reduce
pointer setup, command uploads and synchronous waits. Neither change makes the
blitter transfer pixels faster or guarantees that presentation targets pass.

The [current cursor renderer](../../../ports/gem4xe/adapter/gem-vbxe.c) performs
four synchronous submissions for an ordinary visible move: restore the old
background, save the new background, AND the mask and OR the image. Each uses
the same driver and command arena. Their dependency order fits one list.

Reuse these results and the [2× sensitivity record](../../development/desktop-pointer-scale.json).
There is no new broad baseline milestone. Before changing code, retain the
current build and collect only missing matching measurements: pointer list
counts/setup cost and a two-client 2× latency cohort with the workloads used
for the final comparison. DT6 used earlier sensitivity and is context, not
an interchangeable before/after sample. If a local artifact is missing, rebuild
that exact revision in an isolated directory and rerun only the missing case.

## Timer policy and shared users

Use two fixed platform cadences, not adaptive sampling or a user-selectable
compatibility mode:

| Demand | Physical timer | Pointer capture |
| --- | --- | --- |
| Pointer and/or blitter watchdog, without fine SIO timing | About 4 kHz | Every timer edge while acquired |
| A short SIO phase needing fine timing | About 8 kHz | Every second timer edge while acquired |
| No timer demand | IRQ disabled | None |

The SIO exception preserves short protocol delays. Today
[sio.s](../../../platform/altirraos/sio.s) uses 8, 6 and 10 timer ticks for
COMMAND setup, COMMAND hold and write turnaround. Simply changing these to
4, 3 and 5 preserves nominal durations but doubles free-running phase
uncertainty. In particular, the existing COMMAND hold acceptance window is
650–950 µs. Do not weaken that window to accommodate the mouse change.

Let the SIO driver explicitly request fine timing for the COMMAND sequence,
from before its existing transaction-start timer reset through COMMAND release,
and for write turnaround. Keeping the COMMAND transmission inside that short
window preserves the timer phase used by its hold alarm. Return to 4 kHz for
ordinary data transfer and other waits; acquiring the SIO device alone must not
hold the platform at 8 kHz. Keep the current fine-alarm counts, expressed as
named constants with their clock units. The fine-timing demand is private
platform coordination, not a new Exec gateway or public timer API.

The platform timer owns AUDF1 and its shadow, IRQ acknowledgement and the
capture divider. The SIO driver owns when its fine-timing demand begins and
ends. Define the first-edge and divider behavior for both rate transitions,
including a partially elapsed timer period. Do not count a physical edge twice
or catch up by taking several samples of the same PORTA level. Preserve the
strictly below 1 ms capture-gap gate across transitions. Claim/release must
establish a fresh divider baseline; route changes retain normal electrical
phase tracking.

Change cadence through AUDF1 at a short, serialized boundary. Prove its actual
reload behavior on the pinned emulator; do not assume the first interval after
a write already has the new length. Never add an STIMER reset during an active
serial frame. Preserve the existing safe transaction-start reset and include
it in the gap/phase tests. Keep AUDCTL, serial baud timers and Timer 2's SIO
deadline clock unchanged. Audit saved audio state and every terminal, cancel,
shutdown and failure path so none leaves fine timing asserted after retirement.

Native and ROM emulation IRQ entry continue through the same acknowledged
timer dispatch. Retain bounded serial service around pointer capture and
correct servicing on timer turns that skip capture. `TM_TICKS` continues to
count physical timer dispatches; sample counters count actual captures. Update
trace accounting to distinguish 4 kHz intervals, fine-timing intervals and
transitions, rather than expecting one capture per physical edge everywhere.

The blitter watchdog measures elapsed **VBI ticks**, with its existing 16-tick
deadline. It is not a count of Timer 1 interrupts. Preserve that deadline and
test the changed observation delay, wrap and lost-completion-IRQ path. Normal
blitter completion still uses its own IRQ.

## Pointer batch

Build a complete cursor list after flushing earlier drawing and before starting
any of its records. Use the existing CPU command staging buffer and
`VbxeOwnerSubmit`; keep authorization at the admitted drawing-operation boundary
and the driver's whole-list geometry/work validation. No per-record gateway or
second display-owner check is required. The driver continues to own chain bits,
MEMAC mapping, hardware launch, fences and fault recovery.

| Pointer transition | Ordered records | Hardware launches |
| --- | --- | ---: |
| Visible move | Restore old background → save new background → AND → OR | 1 |
| First show or redraw after background invalidation | Save new background → AND → OR | 1 |
| Hide a drawn pointer | Restore old background | 1 |
| Unchanged, already drawn pointer with valid background | None | 0 |

Restore must consume the old save before the next record overwrites it. This
also handles overlapping old/new pointer rectangles. Retain both prepacked
parity masks, right/bottom clipping and neighboring edge nibbles. Upload masks
before the first list that uses them; account for that cold-start upload
separately from a warmed move.

A move contains four 21-byte records: 84 command bytes. At the maximum nine
packed bytes by sixteen rows, its two copies and two read/modify/write masks
cost at most 1,440 accesses under the existing `VBXE_LIST_WORK` accounting,
well below 8,192. It fits the existing list and VRAM reservations. Do not raise
limits or introduce an additional staging allocation.

Use a common batching helper for `GemDrawingPointer` and the hosted GEM cursor
backend. Prepare candidate geometry locally and adopt the new drawn/save state
only after success. Invalid input must cause no launch or state change. Once a
launched list faults, preserve the existing fault latch and quiescent versus
reset-required cleanup rules; partial hardware execution is not rollback.

Keep this small batch synchronous: one submission with its existing preflight
fence and completion fence, with interrupts enabled during the wait. It returns
when the list finishes, without a new completion signal or cursor-in-flight
state. Pending asynchronous scrolls retain exclusive use of the hardware and
command arena. Drawing that intersects the pointer still restores it before
changing its saved background. Preserve outline/caret ordering and the existing
Layers token lifetime. An intervening background draw legitimately separates
hide and show into different submissions; the one-launch rule applies to an
ordinary pointer move.

## Executable slices

### MP1 — 4 kHz capture with preserved SIO timing

Change `abi/platform-timer.json`, its generator and generated include, the
platform timer and SIO adapter together. Name the normal/fine divisors and
capture ratio. Use unused bytes within the existing 32-byte upper-RAM timer
reservation for fine demand and divider state. Document IRQ masking, NMI
interaction, first/last ownership and timer transition order beside the code.
Keep the current decoder, queues, 2× desktop scaling and input ABI.

Extend the existing shared-timer and mouse trace checks to observe rate changes,
single acknowledgement, capture division and cleanup. Check actual PORTA
capture gaps and counts, not only register values or host motion commands.
Run focused raw/optimized emitted-code cases for:

- Idle and moving ST mouse at the supported minimum spacing, both axes,
  reversals, edge clamping, 10 ms button levels and shifted timer phases. Retain
  the unsupported burst-aliasing negative control. Altirra's fastest existing
  qualifying fixture is 16 scanlines, about 1.029 ms, not an exact 1 ms source.
- Physical SIO at the desktop 57.6 kbaud profile and FASTEST125, including fine
  alarm entry/exit, phase sweeps, cancellation, a selected recovery failure and
  first/last timer ownership in different orders. Preserve the existing
  COMMAND 750–1,600 µs setup and 650–950 µs hold gates, RX/TX byte deadlines,
  payload checksums, absolute timeout units and watchdog lateness bounds.
- Blitter completion, lost IRQ/timeout, VBI wrap and simultaneous timer demand;
  native/emulation routing, saved registers, stack/DP guards and OS restoration.

Use `test_shared_timer.py`, `test_desktop_mouse_boundary.py`,
`test_desktop_pointer_scale.py`, the focused SIO runners and
`test_blitter_irq.py`; extend their meaningful oracles where coverage is absent.
Check generated files and pin actual binaries. Keep this slice atomic: a
divisor-only change must not be committed with broken serial timing. Record
4 kHz normal operation and the duration/rate of every SIO exception explicitly.

Acceptance: normal physical interrupts and pointer captures run at about
3,958.6 Hz; fine intervals preserve approximately the same capture cadence;
all supported electrical transitions/buttons are retained; every measured
capture gap is below 1 ms; existing SIO and lifetime gates pass. No fine demand
survives the last relevant operation. Commit the timer change and its evidence.

### MP2 — One list per ordinary pointer move

Change `ports/gem4xe/adapter/gem-vbxe.c` to use the batch described above,
reusing the existing submit implementation in `platform/altirraos/vbxe.c`.
Avoid broad renderer refactoring. Extend the cursor fixture with independent
pixel and hardware-launch assertions, and run raw/optimized emitted builds.

Cover even/odd coordinates, every screen edge/corner, overlapping and distant
moves, hide/show, unchanged position, invalid requests, disjoint/intersecting
drawing and movement across an XOR drag outline. Compare the complete affected
pixels and saved background, including neighboring nibbles. Verify one upload
and one START for a warmed move, four records in the required order, and no
launch for an unchanged valid pointer. Check pending-scroll exclusion and
selected quiescent/reset-required faults without allowing arena reuse early.

Use `test_gem_cursor.py` and focused desktop drag/scale checks. Compare warmed
pointer setup/validation/upload CPU and total call duration with the retained
baseline and MP1, separating interrupted time and actual blitter busy time when
observable. Keep mask initialization out of the warmed comparison. Commit the
batch and its evidence after the structural, pixel and lifetime gates pass.

### MP3 — Combined desktop measurements

Measure the same two-client desktop with idle, sustained console scrolling and
physical SDFS traffic using `measure_desktop.py`. Use the existing 100 motions
and thirty clicks per load for final latency distributions. Retain the same
2× scaling, content, disk profile, stimulus schedule and second-client workload
in the matching before/after runs. Use the MP1 result to separate timer savings
from batching savings without retaining two runtime implementations.

Report sample-gap median/p95/max, electrical counts and button delivery,
physical IRQ count/time, fine-timing duty, pointer preparation/upload time,
submission count, busy/wait interval and capture-to-visible median/p95/max.
Distinguish pointer-call return from first visible scanout. Report IRQ interval
share with its actual boundaries; do not label it total CPU utilization.
Replay representative combined loads with observers disabled.

Preserve the desktop response targets: pointer/outline p95/max of 40/60 ms at
idle and 60/100 ms under load, with button consumption maxima of 40/100 ms.
Require reduced normal timer overhead and reduced warmed pointer setup cost
against matching measurements, with no newly introduced input, SIO, pixel or
lifetime regression. Investigate a reproducible latency regression before
accepting the slice. Record any still-missed response or 250 ms move-repair
target openly; this work does not expand into scheduler or full-window repair
optimization to make those numbers pass.

Run selected combined drag/focus/close and shutdown checks while the other
client redraws, including input during a pending scroll. Publish compact JSON
evidence in `docs/development/` and a linked record in `docs/history/`. Commit
measurement tooling changes and the evidence separately from implementation.

### MP4 — Refresh the desktop preview

Update the current input/display/desktop contracts with measured sampling,
fine-timing exceptions, cursor completion semantics and remaining limits.
Update plan status and indexes only to the extent the evidence supports.

Build a fresh optional desktop demo with `tools/build_demo.py --desktop`,
including OF816, matching boot XEX/system disk, pinned ROM, notices, a short
guide and checksums. Preserve the five-second autoboot and standard shell/prime
default; the desktop variant keeps its shell and independent application.
Verify the extracted package with `tools/test_demo.py --boot-smoke`, including
mouse movement, focus/drag, keyboard, a physical disk command and clean EXIT.
Keep intermediates and traces outside `exec816-demo.zip`. Record the final
revision and archive SHA-256, commit the documentation/evidence, and provide
the local package. GitHub publishing is a separate action.

## Memory, pins and validation scope

For every slice, report reserved bank-zero deltas against `fbce56f`: target
**0 fixed, 0 root/kernel, 0 per public Task and 0 idle bytes**, including guards,
alignment and unused reserved capacity. Use the generated memory manifest;
unchanged variable payload size alone is not proof. Timer fields fit the
existing 32-byte reservation, cursor records reuse existing CPU/VRAM arenas,
and stack/DP pool sizes do not increase. Check emitted stack usage and guards
even when only ordinary local temporaries change.

Use the compiler selected by [actionc.json](../../../toolchain/actionc.json)
and the PAL 65C816 8×, 4 MiB, VBXE FX 1.26 at `$D600`, ST port 1 profile in
[altirra-gem-vdi.json](../../../toolchain/altirra-gem-vdi.json). Record the actual
mouse-tooling emulator hash from `mouse_input.tooling`, ROM hash, source
revision and any override with every new evidence set.

These are development-tier checks, including targeted deeper timer, interrupt
and transport cases because their behavior changes. Raw/optimized emitted code
and selected integrated execution are required; a full release matrix is not
part of each slice. Broader hosted or physical-hardware qualification remains
separate. Preserve compact result summaries and hashes; large temporary traces
can be removed after extraction without discarding the evidence needed to
reproduce a result.
