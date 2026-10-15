# Presenter quiet turn implementation plan

[GEM plans](README.md) · [Presenter bookkeeping record](../../history/presenter-bookkeeping.md) ·
[Measured baseline](../../development/presenter-bookkeeping.json) ·
[AES contract](../../reference/aes.md) · [Layers contract](../../reference/layers.md)

Status: QT1–QT3 implemented; QT4 measurements/delivery pending.
Development evidence is in the [execution record](../../history/presenter-quiet-turn.md).
This follows the completed [PB1–PB6 plan](presenter-bookkeeping-plan.md).

Shorten the presenter's notification-only turns so it can publish a safe
caller-local UPDATE opportunity sooner. Avoid repeated inspection of unchanged
state, while preserving the current signals, ownership and cache contracts.

## Starting evidence and scope

Use the final PB6 package and passive captures as the baseline; there is no
separate baseline implementation slice. The measured record pins source,
compiler, ROM, emulator, configuration and package hashes. The package is
`build/presenter-bookkeeping/demo`; its older build banner is explained by the
recorded match to the final production sources.

Of 634 observed no-transfer benchmark turns, presenter CPU ranged from
2.28 to 5.39 ms, with a median of 4.39 ms. One median turn breaks down as follows:

| Work | Presenter CPU |
| --- | ---: |
| Readiness queries, counted as an interval union | 1.723 ms |
| Cache maintenance | 1.640 ms |
| `Collect`, including unconditional `SetSignal` | 0.568 ms |
| Gate operations and remaining work | 0.463 ms |
| Total | 4.394 ms |

Visible-damage inspection accounts for 0.560 ms **within** the readiness row.
The representative turn takes 5.301 ms elapsed, including 0.907 ms of interrupts;
the target concerns presenter CPU, not interrupt time. Five final window turns
also exceed the target, at 2.31–4.82 ms CPU. Settled idle already sleeps.

Eliminating the entire measured cache and damage costs would still leave about
2.19 ms before replacement checks. Conditional signal collection therefore
belongs in the same effort. The <=2 ms target is plausible, not a promised
result obtained by adding these estimated savings.

Preserve throughout:

- The existing policy gate, eligible-waiter ordering, caller-local UPDATE and
  RPC fallback. Every successful outer END notification and gate-waiter wake
  remains. An AES signal alone does not prove that no RPC request is queued.
- Normal preemption, current paint/admission budgets and input precedence.
  Cache maintenance still starts at most one new transfer per pass.
- Cache revision, repaint, visibility, pin and transaction ownership rules.
  A scheduling hint only requests inspection; it never certifies valid pixels
  or permission to borrow the display.
- Existing signals and final `Wait` behavior. New hints do not keep the
  presenter awake or add a polling loop.

No priorities, preemption suppression, larger drawing batches, kernel ABI
changes or private kernel operations are included. General input-readiness
cleanup and further window-opening optimizations remain separate follow-ups.

## Slice sequence

| Slice | Change | Completion evidence |
| --- | --- | --- |
| QT1 | Acknowledge signals only when collection has work | No empty collection gateway call; no lost wake |
| QT2 | Reconsider window caches after relevant changes | No repeated geometry inspection of unchanged rejected candidates |
| QT3 | Maintain visible-damage readiness in Layers | Constant-time no-damage query; exact damage/exposure behavior |
| QT4 | Measure the combined result and refresh the demo | Matched costs, application behavior, memory and package record |

### QT1 Make signal collection conditional

Primary file: `lib/console/consoledriver.act`.

Pass the worker's already-established `self` pointer to `Collect`. Read
`self.tc_SigRecvd` as a hint using exactly the existing collection mask:
stop, captured input and the supplied display/desktop bits. If no masked bit
is observed, return the incoming `bits` unchanged. Otherwise call the existing
`SetSignal` acknowledgement and OR its returned bits into `bits`.

Retain bits already consumed by `Wait`; leave request and unrelated signals
pending for their consumers. Do not introduce another `FindTask`, directly
clear Task fields, or expand the acknowledgement mask.

Follow the existing conditional acknowledgement pattern in `DESKINPUT.Boundary`.
The 32-bit read is only a hint: a signal missed across that read remains pending
for the next collection or final `Wait`. The kernel call remains the authority
when acknowledging. The hint must not authorize gate ownership or mutation.

Extend the focused emitted signal tests for arrival before the hint, after the
hint but before `Wait`, and during acknowledgement. Cover already-consumed
`Wait` bits, mixed collected/unrelated bits, and input, display, stop and AES
request wakes. Verify the actual emitted empty path avoids `SetSignal` and
normal stop still completes. Reuse the existing input-wake and AES gate probes;
do not create a second signalling test framework.

Commit: `Avoid empty presenter signal acknowledgements`.

### QT2 Reconsider cache candidates after relevant events

Primary files: `lib/desktop/deskhost.act`, `deskcache.act`, `deskpaint.act` and
`lib/aes/aeswindowstate.act`; audit window creation/change/retirement callers.

Replace the repeated six-window eligibility search in `CachePending` with a
small private candidate mask. Keep it with the existing desktop cache state,
alongside the last observed `scene.rebuilds`. This is work scheduling, separate
from the existing `visualRevision`, `captureAttempt` and cache-validity records.

An actual scene rebuild rearms window candidates once. Content and paint
completion rearm only the affected window. Use an already-resolved window slot
where available; any necessary bounded slot lookup belongs at the change
boundary, not on every readiness query. Avoid pointer division or a Task
identity query to derive a bit.

| Event | Candidate action |
| --- | --- |
| Cache/service initialization | Reset the mask and observed scene state |
| Window creation, geometry/stacking/show/iconification changes | Observe the existing visibility rebuild and reconsider live windows once |
| Native content/title/widget change | Arm the affected window through the existing change path |
| AES BEGIN or hidden/unreported model change | Preserve invalidation; a revision bump alone must not schedule repeated capture attempts |
| Accepted application paint reports | Arm the affected window after END has consumed the journal, including reports with no explicit changed rectangle |
| Native/frame paint completion | Arm the affected window after Layers has retired the paint transaction |
| Temporary scene/display/transfer blocking | Leave unexamined candidates armed; existing completion/wake paths allow later service |
| Window deletion or slot reuse | Clear the old candidate; initialize the new lifetime |

Use existing accepted paint reports as the recheck trigger, without adding a
new rectangle scan to END just to maintain the hint. Partial reports can justify
one new inspection; they do not establish complete pixels. Manager handoff of
an AES frame likewise does not certify completion of application content.

After the common availability checks, inspect only armed candidates and consume
each inspected bit. This includes dead slots, already-attempted revisions,
hidden/covered/dirty/incomplete windows and actual capture attempts. Reconsider
them when one of the events above changes eligibility. Preserve the existing
attempt/revision test and all checks immediately preceding a real capture.
A full paint can complete without a revision or visibility change, so those
two values alone are not a sufficient negative-cache key.

Keep the two repair-slot states and popup capture state authoritative. Preserve
their current precedence and the one-transfer limit. Transfer completion must
not strand an armed candidate, but neither completion nor slot eviction should
reset `captureAttempt` and repeatedly recapture an unchanged evicted window.
Retain existing failed-attempt behavior and pinned-storage lifetime.

Check focused emitted cases: repeated wakes with a covered/incomplete candidate;
later exposure; full and partial application paint completion; hidden model
changes; native frame completion; temporary transfer blocking; deletion/reuse;
and two-slot eviction without recapture churn. Reuse the existing desktop/AES
cache fixtures and one preserved Shell/Files/menu interaction. Require current
pixels, no duplicate application redraw, and zero repeated candidate geometry
work between relevant events. Measure extra caller-side END work as well as
presenter savings, so the optimization cannot merely move the cost.

Commit: `Schedule window cache inspection from state changes`.

### QT3 Maintain visible-damage readiness in Layers

Primary files: `lib/display/layers.act`, `layers-update.inc`, `layers-save.inc`,
`lib/desktop/deskpaint.act`, `abi/layers.json` and generated definitions.

Add a 16-bit visible-damage mask to `LAYERTYPES.Scene`, with one bit for each of
the nine layer slots, including the background. A bit means manager-owned
damage intersects that layer's current visible region. Hidden damage remains
recorded but does not make the presenter runnable. Application-owned pending
repaint is a separate obligation and must not set this mask by itself.

Maintain the summary inside Layers, where damage and visibility change:

- Update the affected bit when marking damage and when paint completion or
  saved-image restoration removes it. Include failed paint/copy retirement.
- Recompute alongside visibility rebuilding after bounds, show/hide, ordering,
  movement and deletion. Clear the summary if visibility is discarded on a
  rebuild failure.
- Initialize background damage correctly, clear deleted/reused slots, and
  handle `FinishHandoff`: manager painting can finish while external repaint
  remains pending.

Keep the intersection rule in one Layers helper. Pass known slots through the
internal mutation helpers where practical; avoid adding repeated full-scene
searches to each mark. Audit every direct write to `dirty`, `damage` and
`visible`, including restore subtraction. `Touch`, `RequirePaint` and `Painted`
must not confuse external pending pixels with manager damage.

`DESKPAINT.DamagePending` then checks the mask after its existing active-token
and paint-lock handling. Keep surrounding service/display availability checks
and current painter/menu ordering. Do not memoize overall `Runnable`: queues,
input and lock release can change independently of drawing damage.

Change the machine-readable layout and regenerate shared definitions; rebuild
affected consumers together with one current layout. Update the Layers contract
to explain the summary and ownership. No application opt-in or new kernel call
is needed.

Extend the Layers fixture with an independent intersection oracle. Cover visible
and fully covered damage, later exposure, partial restore subtraction, failed
paint, external handoff, deletion/reuse and background damage. Require no false
zero and no wake loop caused by covered-only damage. Check the changed layout
with a small raw/optimized emitted probe; run behavioral scenarios optimized.
Measure mutation/rebuild cost as well as the cheaper readiness path.

Commit: `Maintain visible damage readiness in Layers`.

### QT4 Measure the combined result and deliver the demo

Reuse `presenter_control_trace.py`, `window_response_trace.py`,
`measure_frame_exposure.py` and the existing Files/menu/load observers. Extend
passive markers only where needed to count candidate inspections and conditional
acknowledgements. Keep trace output and build intermediates under
`build/presenter-quiet-turn`; do not ship diagnostic instrumentation.

Use the same compiler, ROM, emulator configuration, disk contents and starting
window/cache state as PB6. Record any unavoidable input change and rerun only
the corresponding comparison. Report presenter CPU separately from interrupts,
off-CPU time, actual transfer time and end-to-end UI latency.

Required comparison:

- Quiet no-transfer turns: count, minimum, median, maximum and component CPU;
  empty acknowledgement calls, candidate inspections and damage scans.
- New Window and uncached close: frame/content completion, presenter CPU,
  visibility rebuilds and paint counts. PB6 references are 983 and 401 ms.
- Files keyboard selection and Shell/Files focus: unchanged summary/selection
  pixels and preserved exposure without extra application painting.
- File/View dropdown switches: background/popup reuse and no Files redraw.
- One bounded Counter plus console-output replay: pointer/button completion,
  progress of both background activities, guards and normal EXIT.
- Existing short benchmark replay: quiet-turn population and local/RPC UPDATE
  split. In particular, check the PB6 solid-bar fallback regression rather
  than assuming shorter turns necessarily improve every workload.

Keep the PB6 no-transfer classifier for the <=2 ms target; do not hide expensive
turns by relabelling cache inspection as drawing. Report event-driven rechecks
separately as additional detail. Mark the target met only if the corresponding
matched observations support it; otherwise leave it open with the remaining
costs. These samples establish neither p95 nor hardware qualification. Repeat
only comparisons with a failure, apparent regression or unresolved result.

Record compact measurements in `docs/development/presenter-quiet-turn.json`
and interpretation in `docs/history/presenter-quiet-turn.md`; update plan status,
indices and roadmap. Build the final package once with `tools/build_demo.py`,
including OF816, five-second standard shell/prime autoboot, matching system
disk and pinned ROM/licenses. Deliver `exec816-demo.zip`, checksums and the
launch command; keep manifests, traces and intermediates outside the ZIP.

Commit: `Record presenter quiet turn results and refresh the demo`.

## Memory and validation budget

Target reserved bank-zero delta for **every slice**: fixed **0 bytes**, per
public Task **0 bytes**, idle Task **0 bytes**, including guards, alignment and
unused capacity. No DP or stack reservation increase is planned. Check actual
stack headroom in the focused hosted run.

QT1 adds no persistent state. QT2 needs a small upper-RAM candidate mask and
observed scene counter, nominally five bytes before placement/alignment. QT3
adds one word per Scene in upper RAM; account for generated alignment and
embedded Scene layouts. Report actual native code/data and allocation deltas
per slice. No new VRAM reservation, queue, timer or signal is planned.

Use [development checks](../../contributing/testing.md): affected host/generated
checks and focused emitted behavior, optimized by default. Reserve raw/optimized
duplication for the small changed-layout probe or a suspected compiler defect.
Reuse established ownership, cache and signal fixtures. Do not run the full
qualification matrix or rebuild the delivery package after every slice.
