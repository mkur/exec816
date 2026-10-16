# Menu title repaint and pointer response implementation plan

Status: MT1–MT2 complete; MT3 pending. [Execution record](../../history/menu-title-response.md).

[LR2 results](../../history/layers-rebuild.md) ·
[Recorded measurements](../../development/layers-rebuild.json) ·
[Popup transition plan](popup-transition-plan.md)

Address the two remaining menu recommendations: shorten title repaint
completion and measure pointer response from crossing a heading. Start with
the observer so the preserved LR2 demo supplies a comparable baseline.

The representative LR2 warm File → View switch spends 18.139 ms CPU in six
`DESKPAINT.Pump` calls. Three reach `PaintStrip`, costing 11.510 ms together;
one calls `DESKAPPMENU.Paint`, costing 8.067 ms. These costs are nested, not
additive, and 18.139 ms is not an estimate of removable overhead. The full
switch takes 71.334 ms presenter CPU and about 120 ms sampled visible response.

`DESKMENUPAINT.Paint` continues through left-caption, Windows-caption and
bottom-rule phases after application heading painting. Even a clip covering
only File/View crosses the caption phases and returns for another painter
step. The bottom rule does intersect this damage and must still be drawn.
The existing repeated-heading observer times from host input submission and
compares only rows 32–207: it includes mouse travel and excludes the headings
and the top of the popup.

Keep the saved-popup transaction, Layers damage protocol, renderer budgets,
normal preemption and two-menu-transaction fairness rule. Reuse the existing
menu renderer and painter state; no new cache, request protocol or public ABI
is needed. Commit each implementation slice separately.

## MT1 Observe heading crossings and complete visible feedback

Implemented; six observer tests and the unchanged-package baseline pass.
The historical positioning helper also advances frames; the new cohort uses
one physical burst so sampling begins immediately. [Results](../../history/menu-title-response.md).

Extend `tools/trace_menu_response.py` and `tools/measure_menu_feedback.py`.
Retain the original action sequence and metrics for historical comparisons;
add a small File ↔ View pointer cohort with complete response measurements.

- Record host submission, the first fresh normalized pointer position inside
  the destination heading, native routing of that heading, popup commit and
  title paint retirement. Crossing means the position after
  `DESKMOUSE.Apply`, observed in `DESKINPUT.Fresh`, before possible deferred
  replay. Use the installed title bounds and enabled state with the same
  half-open hit semantics as `TitleAt`; mouse travel phases are not crossings.
- Use existing passive PC/register tracing to observe the coordinate stores
  and routing markers. Resolve observation points from each build's symbols
  and emitted instructions, checking the instruction shape in the host tool.
  Do not insert guest timestamps, breakpoints that stop execution, polling
  Tasks or new target state. If a crossing cannot be resolved, report that
  sample as unavailable rather than substituting host submission or routing.
- Compare the union of the old/new popup footprints and changed title areas
  against settled reference pixels. Keep separate popup-only and complete
  feedback endpoints. Exclude only the cursor's bounded footprint, including
  its previous footprint when needed; retain an unobscured keyboard pixel
  check for the title pixels hidden by the pointer.
- Report travel time, crossing-to-routing delay, routing-to-render retirement
  and crossing-to-complete-visible response. Preserve host-to-popup timing.
  Record the last nonmatching and first matching frame: PAL sampling bounds
  visible completion; exact trace timestamps do not provide subframe pixel
  timing. Charge CPU separately to the old and new endpoints.
- Drain each physical movement before reversing. Associate crossings with
  the requested heading, distinguish deferred replay from fresh motion and
  flag input loss, recrossing or unfinished transitions in the raw record.

Add focused host tests for timestamp wrap, heading edges/gaps, deferred routing,
recrossing and a popup that settles before its title. Run the observer on the
preserved `build/layers-rebuild/demo` package without rebuilding the baseline.
Keep the archive hash and observer version with the new measurements.

Completion: the same physical interaction has both historical and
crossing-relative timing, and a popup match cannot silently stand for a
completed title repaint. No production behavior changes in this slice.

Commit: `Measure menu response from pointer heading crossings`.

## MT2 Complete small title damage without empty painter steps

Implemented. Small title clips finish in one painter call; seven focused
title cases, 321 AES checks and the existing input/pixel fixture pass.

Refactor `lib/desktop/deskmenupaint.act`, with a small caller adjustment in
`deskpaint.act` only if needed. Keep application rendering in
`DESKAPPMENU.Paint` and the existing `OP_MENU_DRAW` batch.

- Decide which bar components intersect the current clip before entering
  their draw phases. Skip disjoint left-caption and Windows-caption phases
  immediately, without C drawing calls or a continuation return.
- When a bounded application-title batch completes, finish its intersecting
  bottom-rule segment in that invocation and return complete if nothing
  remains. The ordinary File/View title clip should take one `PaintStrip`
  call rather than three, removing the associated extra service boundaries
  and pointer-presentation attempts.
- Preserve a continuation when the object renderer reports more work. Keep
  its four-object/80-character limits and current index/phase state. Full-bar
  repaint and native captions retain bounded real drawing steps; do not
  drain an arbitrary menu tree in one call.
- Keep old/new heading damage precise. Adjacent headings already covered by
  one damage rectangle share its batch; separated rectangles remain separate
  paint obligations. Do not widen them across unrelated headings merely to
  achieve a one-call count.
- Retire only rectangles actually painted, through the existing
  `AdvancePaint`/`Finish` path. Preserve pending damage, frozen source state,
  failure recovery and display-completion gates. Input service remains at
  existing boundaries between real work units; do not remove it globally or
  increase the presenter's four-step allowance.

Extend the existing optimized AES-menu fixture and independent pixel oracle
for adjacent and separated heading changes, a partial title clip, full-bar
repaint, application/native caption transitions and renderer continuation.
Check a failed draw leaves repaint obligations intact. Retain its popup cache
hit/miss, deferred input, source-change and fairness coverage. Run the affected
host checks and this fixture; no separate broad desktop matrix is needed.

Completion: a normal title clip completes in one painter call, title/bar
pixels match the oracle, and continuations and failures preserve damage.
Measure actual call and CPU reductions rather than assuming all 18 ms vanish.

Commit: `Finish small menu title repaints without empty phases`.

## MT3 Compare response and refresh the demo

Build one final OF816 desktop package with `tools/build_demo.py --gem-desktop
--release-compiler`, using the same compiler, ROM and emulator configuration
as the MT1 baseline. Keep five-second autoboot, the matching system disk,
licenses and checksums. Keep traces and build intermediates outside the ZIP.

Run the original 18-action capture and the new crossing cohort with the same
observer on both packages. Compare warm File/View hits separately from the
three-heading cache-miss sequence. Retain open, highlight, dismiss and native
menu controls, plus one existing Counter-progress case for fairness.

Report painter calls, input/pointer boundaries, presenter CPU, render
retirement and both visible-response endpoints. Require correct complete
pixels, unchanged expected cache transfers, zero incidental Files paints and
no timed disk traffic in the idle comparison. Investigate a behavioral failure
or material regression with only the affected case repeated. Preserve guard,
normal EXIT and OF816 autoboot checks and verify archive checksums.

Use minimum/median/maximum for the small cohorts, not a p95 claim. A CPU saving
without a sampled visible improvement is still reported as such. Save compact
measurements under `docs/development`, interpretation under `docs/history`,
update indices and slice status, and provide the demo launch command.

Commit: `Record menu title and pointer response results`.

## Resource and validation scope

Expected reservation delta in every slice: **0 fixed bank-zero bytes, 0 per
public Task, 0 idle**, including guards, alignment and unused capacity. No
new Scene, VRAM, DP, stack or upper-memory reservation is planned. Record
actual code/data changes and local-stack/observed stack costs in the result.

Use [development checks](../../contributing/testing.md). Optimized emitted
behavior covers the painter change; raw checks are needed only if a
compiler-facing defect emerges. This work does not qualify real hardware or
establish worst-case latency bounds.
