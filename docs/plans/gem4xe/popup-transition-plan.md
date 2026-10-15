# Popup replacement implementation plan

Status: PT1–PT2 implemented; PT3–PT4 pending.

[Design](popup-transition-design.md) ·
[DB3 results](../../history/dropdown-bookkeeping.md) ·
[Baseline record](../../development/dropdown-bookkeeping.json) ·
[Layers contract](../../reference/layers.md)

Implement one scene transaction for switching headings within the same GEM
application menu. A valid saved background permits one final visibility
rebuild; a cached replacement popup permits two consecutive whole-image copies
without an intermediate hide/show or application repaint.

The baseline warm switch is 180.4 ms elapsed and 121.5 ms presenter CPU. The
representative background-retirement-to-popup-copy gap is 48.2 ms. Reduce the
bookkeeping behind these costs while retaining the design's damage, input and
cache lifetime rules. First open, dismissal, native menus and invalid-save
fallback remain on their current paths.

When implementation starts, commit the design and plan first, then commit each
slice below after its focused checks. PT1 and PT2 provide tested primitives;
production menu switching adopts them only in PT3, together with input and
fairness handling. Do not introduce a configuration flag or a second permanent
implementation profile.

## PT1 Add the Layers saved replacement transaction

Implemented; [development evidence](../../history/popup-transition.md).

Primary files: `abi/layers.json`, generated `layertypes.act`,
`lib/display/layers-save.inc`, transaction helpers in `layers-update.inc`,
`tests/programs/layers-save-checks.inc` and `tools/test_layers.py`.

- Add `UPDATE_SAVED_REPLACE` and three named finish outcomes:
  `REPLACE_CLEAN`, `REPLACE_DIRTY`, `REPLACE_REPAIR`. Generate constants through
  `tools/generate_layers.py`; preserve all record sizes and offsets.
- Add `BeginSavedReplace(scene, overlay, nextBounds, tokenOut)`. Admit once,
  require a current unpinned background covering old and new bounds, then
  claim the token before mutating state. Reuse `copySource`/`copyTarget`, pin
  the save, and leave committed bounds, shown state, stacking and visibility
  unchanged. BUSY, EXHAUSTED and unusable-save results leave state and output
  token unchanged. Trust the caller's live layer handle and admitted geometry.
- Add `FinishSavedReplace(scene, token, outcome)`, called after transfer
  quiescence. CLEAN commits a complete current popup; DIRTY commits its new
  bounds for ordinary painting; REPAIR retains old geometry and marks both
  possibly touched rectangles. A stale background forces REPAIR. Generic
  `Finish` must not bypass the new transaction's commit/repair cleanup.
- For successful background restoration, subtract manager damage only inside
  `copySource`, retaining damage on bounded subtraction overflow. Preserve
  external pending repaint. Edit popup damage and geometry directly, then
  rebuild visibility once; do not call `Show`, generate temporary coverage
  damage, or update summary bits against an intermediate scene. Preserve
  fail-closed behavior if the final rebuild fails.
- Retain a valid background for subsequent headings. Release its pin and
  token exactly once at completion; stale tokens cannot affect another
  transaction. Document the new ordinary-library contract in
  `docs/reference/layers.md` when implemented.

Extend the existing emitted Layers fixture with independent final geometry,
visibility and damage expectations: overlapping/disjoint rectangles, changing
sizes, CLEAN/DIRTY/REPAIR, pre-existing manager damage, preserved application
pending damage, stale background, bounded-damage overflow, busy/exhausted
admission and stale finish. Assert old geometry and unchanged rebuild count
while busy, then one rebuild on a successful commit. Retain guards and normal
OS return.

Run host checks, generator `--check` and
`tools/test_layers.py --mode opt --output build/popup-transition/pt1-layers`.
No raw matrix is needed for constants and unchanged record layouts. If a
compiler-facing layout or calling-convention change proves necessary, add only
the affected small raw/optimized probe.

Memory: no persistent storage growth; fixed/per-Task/idle reserved bank-zero
deltas **0/0/0 bytes**. Record native code and local stack changes.

Commit: `Add a Layers transaction for saved popup replacement`.

## PT2 Implement the bounded asynchronous cache continuation

Implemented; [development evidence](../../history/popup-transition.md).

Primary files: `lib/desktop/deskmenucache.act`, with focused presenter/cache
fixture support. Keep ordinary production menu admission unchanged in this
slice; exercise the new path through the fixture.

- Add a replacement entry taking the target popup key and bounds. Layers
  performs save/scene admission; the adapter matches the existing two popup
  slots and checks transfer alignment/capacity. Freeze the target key and
  reuse the existing token and slot bookkeeping, adding only the phase data
  needed across completions. No heap allocation or new cache slot.
- Let the shared popup-copy helper take an explicit rectangle, so replacement
  copies use staged bounds while ordinary capture/paint uses committed bounds.
  Copy old background from its offset within the retained union save. Pin a
  matching popup image before launching either transfer.
- Extend `Pump`/`Foreground` to progress background restore → optional popup
  copy → completion. Keep one scene token and policy exclusion across the
  transfer-free gap. At notified background completion, submit the new image
  immediately if still usable. A cache miss commits DIRTY without waiting for
  capture; retain ordinary idle capture policy afterwards.
- Distinguish background failure from popup-only failure. Map them to PT1's
  REPAIR or DIRTY outcome respectively; recheck invalidation before the second
  copy and final completion. Partial/failed transfers require ordinary repair,
  not an assumption that pixels stayed unchanged. Keep pins/token on an
  unquiesced display until existing recovery establishes safe release.
- Return one completed transition result for PT3 to adopt under the closed
  policy gate. Do not reopen admission between Layers completion and menu
  snapshot adoption. Remember only proven restored exposure, retain a usable
  save, and update existing hit/miss/byte counters once per operation. A miss
  must not trigger a redundant cache lookup or double-counting when ordinary
  painting resumes.

Use one optimized presenter fixture with independently checked VRAM pixels
for a hit, miss and different-size replacement. Inject failures before/after
background completion and during popup copy; inspect token, pin and damage
state before allowing recovery. Include a save invalidated between copies and
a stale completion after a later transaction. Reuse existing display fault
hooks or fixture-only injection; add no production fault controls or polling.
Run host checks and the affected emitted cases; rerun PT1 only if its code or
contract changes.

Memory: count new fixed upper-memory fields against the design's **32-byte
total target**. No Scene layout, VRAM, Task, DP or stack reservation growth;
reserved bank-zero deltas **0/0/0 bytes**.

Commit: `Chain popup cache copies under one scene token`.

## PT3 Integrate menu state, input deferral and fairness

Primary files: `deskmenu.act`, `deskappmenu.act`, `deskhost.act`,
`deskpaint.act`, `deskinput.act` and `lib/console/consoleinput.act`, plus the
worker's existing readiness checks where needed.

- In `DESKMENU.Advance`, try combined replacement before the ordinary restore
  when pending/current menus share the same current GEM owner and lifetime.
  Freeze the requested heading/key without prematurely changing the committed
  paint snapshot. On an ineligible save, use the existing path immediately.
- Add a small snapshot-adoption helper shared with existing menu state code.
  On completion, publish heading/selection/open state, dirty only the old/new
  title segments, and record the resulting scene revision. A clean cached popup
  must not fall through `Open`, `Show`, `TopChrome` or ordinary full-popup
  invalidation. A dirty commit enters the normal painter with the matching
  target key. Preserve newer menu revision damage and existing owner-change
  cancellation and durable `MN_SELECTED` rules.
- During replacement, retain pointer gesture events in the existing AES input
  queue while still capturing/normalizing fresh position once. Drain those
  events after completion, preserving button edges and loss handling. Prevent
  clicks from reaching the covered window or changing the in-flight target.
- Gate keyboard dequeue before `INPUT.Take`. Keep the existing pending hint
  when input is deferred: a short/zero deferred drain is **not** an EMPTY
  observation. Resume on transition completion without requiring another key
  or signal. Keep this pending input out of the runnable predicate while it
  cannot progress, so the presenter waits for completion instead of spinning.
- Let the existing `MenuContinuation` complete/continue the transfer before
  unrelated controls. Reuse `DESKPAINT`'s menu-turn accounting through a small
  shared helper: admission of a combined replacement counts as one preferred
  transaction. After two, let ready ordinary work run before another; do not
  block menus solely because no ordinary work exists. A cache-miss repaint is
  an ordinary subsequent paint transaction. Preserve the existing worker
  budget, input boundary and normal Task preemption.

Extend the existing AES menu fixture (`tests/programs/aes_menus.c` and
`tools/test_aes_menus.py`), run through `tools/test_aes_server.py --suite menus
--mode opt --output build/popup-transition/pt3-menus`. Add bounded case selection
if needed to isolate the changed transition. Exercise rapid
heading keys, queued Return/Escape, held-button movement/release, pointer loss,
owner/menu replacement, and exact menu choice delivery. Queue input during both
copies and verify no lost wake, click-through or wrong-heading activation.
Add one ready-background-paint case to verify the two-turn boundary and one
completion-wait case to verify absence of repeated runnable turns. Check menu
and restored-background pixels with the existing independent menu oracle.

Run host checks and these optimized integration cases. Include ordinary
open/dismiss, native menu and invalid-save fallback in that same fixture;
retain stack/domain guards and cleanup. Do not run a complete desktop or
filesystem qualification matrix.

Memory: include any additional scalar fields in the same 32-byte upper-memory
target. No additional queue, signal, timer, Task or VRAM reservation. Reserved
bank-zero deltas **0/0/0 bytes**.

Commit: `Switch GEM headings with one committed scene transition`.

## PT4 Measure the result and deliver the demo

Reuse `build/dropdown-bookkeeping/demo` and the recorded DB3 18-action capture
as the baseline; no separate baseline slice. Keep compiler, ROM, emulator,
machine, disk settings and menu inputs matched. If cleanup removed artifacts,
recover the exact recorded version or rebuild it with the recorded inputs;
do not silently compare different pins.

Extend `tools/trace_menu_response.py` to recognize the new begin/finish and
copy phases. Classify transfers by actual phase, since both may now originate
inside `Pump`. Keep existing elapsed/CPU boundaries and separate nested costs.
Measure background-completion observation → new-copy submission on both
versions; retain the historical retirement-gap measurement separately if the
new combined operation has no equivalent intermediate retirement point.

Build one final package:

```sh
python3 tools/build_demo.py --gem-desktop --release-compiler \
  --output build/popup-transition/demo
python3 tools/trace_menu_response.py --bundle build/popup-transition/demo \
  --output build/popup-transition/menus
```

For eligible warm switches, require one visibility rebuild, two whole-image
copies, no intermediate hide/show damage pass, correct final pixels and zero
Files paints. Compare presenter CPU, copy gap and end-to-end response. Keep
the three-heading/two-slot cache-miss sequence, physical pointer travel,
highlight, open and dismiss results separate. Investigate behavioral failures
or repeatable regressions in those controls; repeat only affected cases.
If structure improves without visible latency improvement, report that limit
instead of claiming the response goal is met.

Report minimum/median/maximum for the small cohorts, not p95. Preserve the
one-PAL-frame sampling limitation and the distinction between observed copy
submission/completion and pure DMA time. Record the current compiler/platform
identities, actual code/data growth, stack observations and all reservations.
PT4 itself adds no target state; reserved bank-zero delta **0/0/0 bytes**.

Save compact measurements as `docs/development/popup-transition.json`, the
execution record as `docs/history/popup-transition.md`, and update indexes and
slice status. Verify the final ZIP's checksums, OF816, five-second autoboot,
matching system disk, pinned ROM and license notices. Keep traces, manifests
and build intermediates outside `exec816-demo.zip`; provide the package and
`build/popup-transition/demo/launch-altirra.command` in delivery.

Commit: `Record popup transition results and refresh the demo`.

## Validation and memory scope

Use the [development tier](../../contributing/testing.md). Each code slice
runs host checks and the focused emitted cases named above; retain passing
results when their inputs are unchanged. Documentation-only commits require
content/link checks. Additional raw tests are for an actual compiler-facing
change or defect, not duplicate system runs.

For every slice, report fixed, per-public-Task and idle bank-zero reservation
deltas separately, counting guards, alignment and unused capacity. All are
expected to remain zero, as are VRAM, DP and stack reservation deltas. The
upper-memory target covers all slices combined. Avoid a large refactor to
force that target; document an evidence-based adjustment if needed. These
development checks do not qualify hardware or establish worst-case timing.
