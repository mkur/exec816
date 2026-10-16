# Popup visibility rebuild analysis

[Current measurements](damage-retirement.md) ·
[Per-layer evidence](../development/popup-visibility-analysis.json) ·
[Layers contract](../reference/layers.md#saved-scene-rectangles)

The next useful visibility optimization is a small **occlusion-aware affected
layer filter** for saved-popup replacement. Filtering only by intersection with
the old/new popup bounds would avoid very little work in the measured scene.
Accounting for intervening opaque windows identifies about **3.5 ms of existing
geometry work** that could be skipped, before classification and retained loop
costs. This is an opportunity estimate, not an implemented speedup.

Production code and the demo are unchanged. The analysis reuses DR2's clean
`cbc0a16b` package and passive trace, plus a read-only File/View scene probe of
that same package. The complete keyboard switch still takes about 57.6 ms
presenter CPU and reaches matching sampled pixels near 100 ms. Its scene commit
costs 13.835 ms, including 11.350 ms in `Rebuild`.

## What the rebuild actually does

`Rebuild` resets visibility and recomputes the runnable-damage bit for all nine
slots. Six are shown in this scene; three are unused. Each shown slot starts
from its full bounds, subtracts nearer occluders first, and copies intermediate
regions back from `Scene.work`. Dirty summaries then scan the final visibility.

The first complete keyboard switch breaks down as follows. Costs include the
slot's geometry work and its final `UpdateDamage`, with nested subtraction
costs counted only once.

| Slot | Role | CPU | Subtractions | Visibility changes? |
| --- | --- | ---: | ---: | --- |
| 0 | Menu bar | 0.287 ms | 0 | No |
| 1 | Popup | 0.216 ms | 0 | Yes |
| 2 | Shell | 1.504 ms | 2 | No |
| 3 | Desktop application | 5.984 ms | 3 | Yes |
| 4 | Files `SYS:` | 0.874 ms | 1 | Yes |
| 5–7 | Unused | 0.331 ms | 0 | No |
| 8 | Background | 2.141 ms | 4 | No |
| | Final loop/revision tail | 0.014 ms | | |

The 11.350 ms total comprises **5.633 ms in region subtraction**, **2.778 ms
in damage-summary maintenance**, and **2.939 ms in other construction, copying,
lookup and loop work**. The desktop's damage scan alone costs 1.835 ms inside
its 1.888 ms summary update. The scene can have no runnable paint while retaining
damage hidden under windows; that hidden damage accounts for real scan work.

This distribution is stable across all three complete keyboard and three
complete pointer samples. The table partitions the existing trace at successive
`UpdateDamage` returns, matching the fixed slot iteration order. Some prologue
and loop costs therefore accompany the slot intervals; they are not all removed
by skipping a slot's geometry.

Source: [Rebuild and damage summaries](../../lib/display/layers.act),
[saved-popup commit](../../lib/display/layers-save.inc).

## Why the obvious bounds filter is insufficient

The File popup occupies `(136,11)–(296,123)`; View occupies
`(200,11)–(344,68)`. Their enclosing rectangle is
`x=[136,344), y=[11,123)`. Front-to-back order is popup, menu bar, Files, Shell,
desktop, then the implicit background.

- The menu bar ends at row 11, touching rather than overlapping the popup.
- Files starts at row 24 and covers the entire width of the possible change
  below that row. Files visibility must change.
- Shell starts at row 29. Its bounds intersect both popup positions, but Files
  covers those intersections. Shell's actual visible region remains the same
  left-hand strip, `x=[32,120), y=[29,202)`.
- The desktop remains exposed between rows 11 and 24. Its visibility changes
  there, so its comparatively expensive rebuild cannot simply be omitted.
- The implicit background remains completely covered by desktop and menu bar.

A bounds-only selector retains popup, Shell, desktop, Files and background.
It skips just the bar and unused slots: **0.618 ms including summaries, or
0.357 ms of geometry work when summaries are retained**. New classification
overhead would consume part of that small budget.

The independent pixel comparison finds actual visibility changes only in
**popup, Files and desktop**. In particular, "currently invisible" alone is
not a sufficient general skip rule: moving an occluder can expose a previously
hidden layer. Background is safe here because unchanged opaque layers still
cover the entire possible change.

## A bounded conservative selector

Use one temporary rectangle enclosing the old and new popup bounds, and one
local slot mask. Walk the existing stacking order from front to back, treating
the background as the final layer.

The popup is always selected. Other layers above it retain their visibility,
but still mask the possible change below. For each shown lower layer, select
it if its bounds intersect the remaining possible-change rectangle. Then
shrink that rectangle where the current opaque layer covers a complete edge.
Skip subtracting the popup itself from this running rectangle.

The shrink operation retains a **conservative enclosing rectangle**. A window
covering the full width of its bottom portion can raise the bottom boundary;
corresponding top/left/right cases work similarly. Complete coverage makes it
empty. An interior hole or disconnected remainder keeps the larger enclosing
rectangle, accepting extra rebuilds instead of creating a region list.

For this scene:

| After considering | Remaining possible change | Decision |
| --- | --- | --- |
| Menu bar | `x=[136,344), y=[11,123)` | Preserve bar |
| Files | `x=[136,344), y=[11,24)` | Rebuild Files |
| Shell | `x=[136,344), y=[11,24)` | Preserve Shell |
| Desktop | Empty | Rebuild desktop |
| Background | Empty | Preserve background |

This is conservative because changed visibility can occur only within the old
or new popup footprint. Every unchanged opaque layer removes its covered
pixels from the possible change reaching lower layers. Replacing that remainder
with its bounding rectangle can add false positives but cannot hide a real
change. The popup retains its stacking position throughout the transaction.

Reuse the current per-layer construction for selected slots, including its
nearest-occluder order and fail-closed behavior. General show/hide, reorder,
move and other mutations should continue to select all slots. No new public
operation, persistent validity flag or pre-popup region cache is required.

## Damage and transaction boundaries

Preserving a visibility list does **not** automatically preserve its damage
summary. `FinishSavedReplace` also subtracts restored pixels from manager damage,
including lists belonging to layers whose visibility is unchanged. Overflow
retains conservative obligations. External pending repaint remains independent.

For the first implementation, retain the existing summary refresh for every
slot. Use the selection mask only for visibility construction; do not retain
the old `visibleDamage` bits blindly. A more selective summary rule would need
its own proof about old runnable damage, successful retirement and overflow.
It is not included in the saving estimate below.

Keep one scene revision increment, final geometry publication, cache
certification and token/pin release under the current transaction. CLEAN and
DIRTY replacement both need correct visibility; REPAIR keeps old geometry and
its existing damage path. A failed region construction must still clear all
visibility and the summary before returning failure, including retained lists.

## Expected benefit and recommendation

Selecting popup, Files and desktop would retain **four of the ten** observed
region-subtraction calls. The six skipped slots currently consume 4.263 ms,
including 0.767 ms of summary maintenance that the first slice should retain.
That leaves **3.496 ms of geometry/loop budget** in the representative sample,
and **3.496–3.539 ms across all six samples**. Some shared loop work remains and
the selector adds work, so net savings must be smaller.

Even with zero classification cost, this suggests a rebuild near 7.85 ms rather
than eliminating the entire 11.35 ms. It does not establish an 80 ms complete
feedback result. The dominant desktop construction and its damage scan remain.

Proceed with a small implementation plan for this selector and reuse of the
existing rebuild loop. Do not introduce general incremental region patching:
that adds fragmentation/capacity handling beyond this change. A complete
pre-popup visibility snapshot could avoid more construction but would add up
to **6,930 bytes for nine Region records alone**, plus invalidation/lifetime
rules; it is a separate option if a larger gain later warrants it.

The proposed selector needs temporary locals only. Expected reserved bank-zero
delta is **0 fixed, 0 per public Task, 0 idle bytes**, including guards, alignment
and unused capacity. Actual emitted code size, local stack cost and net CPU
saving must be measured during implementation.

## Evidence scope

The preserved DR2 timing capture and the new geometry probe use the same ZIP
SHA-256, `ade55940e2468bd000ece5a22266f2b23deac34f47ad1827f708c305ff6d33d3`.
The probe reads scene records after settled File/View interactions; it does not
alter guest memory or time a modified implementation. Its normal EXIT and guards
pass. The timing numbers come from the original passive capture, not debugger
pauses or the new snapshot run.

An independent host pixel oracle checks the captured visible regions against
the opaque stacking model at every screen position. A host-only selector model
also checks 128 small generated legal scenes, including varied popup ranks and
hidden layers, plus five explicit edge/coverage cases. It misses no changed
layer and deliberately selects 44 extra layers across the generated cases.
These feasibility checks are not emitted-code validation of a future selector.

Artifacts: `build/popup-visibility-analysis`, with the successful read-only probe
in `scene-checked`. Compact geometry, per-slot timings, gross budgets and input
hashes are in the linked evidence. No production code, ABI, toolchain pin or
demo package changed; no qualification matrix ran.
