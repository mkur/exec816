# Dialog drawing costs and batch sizing

[History](README.md) · [RP changes and elapsed comparison](rectangle-overhead.md) ·
[Measurements](../development/dialog-drawing-batches.json) ·
[Display ownership contract](../reference/display.md#delegated-renderer-access)

Follow-up: the [short drawing-unit experiment](drawing-preemption.md) tests
deferred Task switching while retaining all eight units. The measurements and
batch models below describe the preceding RP5 image.

Repeated ownership is worth reducing, but it is not the largest cost in the
current five-object dialog. The eight Enter/Leave pairs take **7.62 ms CPU**;
rendering, command construction and uploads take **18.34 ms CPU**. Including
outer UPDATE, visibility and event handling, other caller bookkeeping takes
**30.14 ms CPU**, with another **1.70 ms** in completion polling. That broad
bookkeeping total dominates drawing, but much of it is outside the per-object
transactions and cannot be eliminated by grouping them.

These passive captures use the unchanged RP5 OF816 package, SHA-256
`e147eb25f9a3b8d873998a33cb882bae1c232d3f99ad7833e13243f9d155425a`,
with the existing PAL/8x 65816/VBXE configuration, canvas (152,56,480,160) and
stationary pointer (630,230). All five reported medians match the preceding
untraced runs. Analysis covers three measured batches: **120 dialogs idle**
and **60 beside Counter**. Warmup, calibration and reporting are excluded.
Guest code, scheduling and reservations have not changed.

## Complete operation versus physical drawing

The following elapsed intervals are disjoint. Values are cycle-observed means
per dialog, not the VBI-quantized medians or UI latency percentiles.

| Phase | Idle elapsed | Beside Counter |
| --- | ---: | ---: |
| `objc_draw`, including all eight physical transactions | 48.383 ms | 53.322 ms |
| UPDATE Begin/End pair | 33.236 ms | 40.938 ms |
| Benchmark visibility checks | 6.378 ms | 11.367 ms |
| Event polling | 3.969 ms | 5.505 ms |
| Other benchmark work | 1.121 ms | 1.193 ms |
| **Whole operation** | **93.087 ms** | **112.325 ms** |

Idle time consists of 50.183 ms benchmark Task CPU, 32.172 ms on other Tasks
and 10.731 ms in native interrupts on the benchmark Task. With Counter these
become 51.477, 49.792 and 11.056 ms. CPU charge includes kernel calls and bus
stalls. The presenter consumes 26.485 ms CPU per idle operation, within the
other-Task interval; it must not be added to elapsed time again.

In particular, 25.021 ms of the idle UPDATE pair is off-Task time. An ownership
batch inside `objc_draw` does not remove that pair or its service protocol.

## Exclusive caller CPU

| Work | Idle CPU per dialog | Scope |
| --- | ---: | --- |
| Object rendering and command construction | 15.795 ms | Inside physical drawing |
| Command upload/encoding | 2.549 ms | Inside physical drawing |
| Completion polling | 1.700 ms | Inside physical drawing |
| Eight Enter/Leave pairs | 7.616 ms | Repeated ownership |
| Unit/pointer glue and submission/fence bookkeeping | 2.414 ms | Repeated around drawing |
| Object traversal, clipping and preparation | 4.164 ms | Inside `objc_draw`, outside borrowed callbacks |
| UPDATE, visibility and event polling | 15.030 ms | Outside `objc_draw` |
| Other application work and arithmetic | 0.915 ms | Outside `objc_draw` |
| **Total** | **50.183 ms** | Rounding applies |

The first six rows total `objc_draw`'s 34.238 ms CPU. Its remaining elapsed
time is 6.772 ms on other Tasks and 7.372 ms in interrupts. Completion polling
measures software execution, not exact blitter BUSY duration.

Each dialog has **8 borrows, 16 fence calls, 8 command uploads and 8 submissions**.
There are 14 solid-fill calls: two for each of four background strips, two for
the small box and two for each button. The label is the remaining unit.
Ownership costs about **0.95 ms CPU per pair**. Other per-unit bookkeeping is
also relevant, although necessary list submissions/completion work cannot all
be removed.

## Existing unit durations and preemption

The known-held interval runs from successful `DisplayEnter` return to
`DisplayLeave` entry. It is a lower bound on full ownership duration: some
ownership bookkeeping is outside those markers. The wider Enter-entry to
Leave-return envelope can include admission waiting or execution after release.

| Unit | Idle known-held CPU, mean | Longest known-held elapsed, idle | Longest known-held elapsed, Counter |
| --- | ---: | ---: | ---: |
| Background top, 16 rows | 2.484 ms | 3.776 ms | 10.760 ms |
| Background middle 1, 16 rows | 2.834 ms | 17.147 ms | 17.180 ms |
| Background middle 2, 16 rows | 2.578 ms | 9.313 ms | 22.814 ms |
| Background bottom, 16 rows | 2.464 ms | 3.778 ms | 15.390 ms |
| Label | 2.950 ms | 3.748 ms | 15.175 ms |
| Small box | 2.261 ms | 2.917 ms | 8.959 ms |
| OK button | 2.962 ms | 3.760 ms | 20.101 ms |
| Cancel button | 3.649 ms | 5.336 ms | 16.787 ms |

Preemption materially extends ownership. In the slowest idle unit, **3.747 ms
CPU + 0.965 ms interrupts + 12.435 ms off-Task = 17.147 ms** held. The slowest
Counter unit is **2.611 + 0.666 + 19.537 = 22.814 ms**. Across the eight units,
off-Task time while definitely holding the display averages 5.476 ms idle and
7.244 ms beside Counter. These are observed tails, not universal bounds.

This supports investigating deferred task switching during a *short physical
batch*. It does not support making the whole AES UPDATE or an arbitrary
`objc_draw` non-preemptible. Acquisition may wait, and release should publish
the free renderer before pending switching is allowed. Interrupt delivery must
continue. Any such change needs a separate ownership/wait/failure-path review
and focused validation; the baseline contract permits preemption while drawing.
Deferring other Tasks can move their work into later UPDATE waits, so the held
time reduction is not a guaranteed equal reduction in whole-operation time.

## Batch-size estimates

The offline model merges adjacent units and subtracts only intermediate
Enter/Leave **CPU**. It retains object traversal between units, all draw calls,
all existing uploads/submissions and cursor/fence work. It excludes scheduling
and interrupt time from the prediction. It estimates CPU savings and CPU spent
holding ownership; it does **not** predict new elapsed times or p95 latency.

| Grouping | Acquisitions | Ownership CPU saved, idle | Longest modeled held CPU, idle maximum | Counter maximum |
| --- | ---: | ---: | ---: | ---: |
| Current units | 8 | 0 | 4.326 ms | 5.488 ms |
| One per object, combining the four background strips | 5 | 2.915 ms | 13.274 ms | 14.519 ms |
| Four adjacent pairs | 4 | **3.852 ms** | **7.970 ms** | **10.086 ms** |
| Background; label + small box; buttons | 3 | 4.795 ms | 13.274 ms | 14.519 ms |
| Whole dialog | 1 | 6.680 ms | 28.359 ms | 29.898 ms |

**If batching is pursued, start with four batches:** upper background half, lower background half,
label plus small box, and the two buttons. Their mean modeled held CPU is
5.386, 5.111, 5.878 and 7.262 ms idle. Each group also fits within the existing
32-row callback height limit. This is a useful initial shape for this dialog,
not a universal two-object rule.

Going from four batches to one saves only another **2.828 ms ownership CPU**
while increasing the longest modeled held section from about 8 to 28 ms idle.
With interrupts, the whole-dialog reservation would be longer still, even
without task switching. The extra foreground gain is small relative to the
delay imposed on pointer/presenter drawing. An initial target of roughly
**5–8 ms drawing-task CPU per batch**, with measured loaded outliers around
10 ms, is more reasonable than treating the entire tree as one transaction.
This is a sizing target, not an implemented timer or a guaranteed wall limit.

Combining the background's two 16-row callbacks into one 32-row callback can
also remove repeated object setup; grouping children can reduce forced final
submissions. Those additional gains are unmeasured and excluded from the
ownership-only estimates. Keep the existing **64-record / 8192-work-unit** list
limits: lists can drain inside a batch without releasing display ownership.
Measure the resulting implementation before enlarging batches further.

The pointer was outside the canvas throughout these captures. Pointer overlap,
motion, fragmented visibility and other trees still need checks when batching
is implemented. No new production batching or scheduling policy is introduced
by this analysis.

## Reproduction and validation

Run the two `tools/trace_g4bench.py` commands recorded in the measurement JSON,
then use [the offline analyzer](../../tools/analyze_dialog_batches.py):

```sh
python3 tools/analyze_dialog_batches.py --trace build/rp-dialog/trace-idle \
  --output build/rp-dialog/trace-idle/dialog-batches.json
python3 tools/analyze_dialog_batches.py --trace build/rp-dialog/trace-counter \
  --output build/rp-dialog/trace-counter/dialog-batches.json
```

The analyzer checks eight complete successful transactions per measured dialog
and preserves inter-unit traversal when modeling combined ownership. Four host
tests cover the merge arithmetic, preemption exclusion, unchanged single units
and tail statistics; six existing trace-parser tests also pass. Both complete
five-row package runs save their reports, close normally, run HELLO and EXIT
with intact guards and no remaining live Tasks; Counter advances in its run.
This is development measurement, not full hosted-system or hardware qualification.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards/alignment/unused capacity. Guest upper RAM, VRAM and stack capacities
are unchanged. Large traces stay under `build/rp-dialog/`.
