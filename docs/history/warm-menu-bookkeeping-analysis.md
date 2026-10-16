# Warm menu bookkeeping analysis

[CG3 results](clipped-menu-text.md) ·
[Measurements](../development/warm-menu-bookkeeping-analysis.json) ·
[Popup transaction design](../plans/gem4xe/popup-transition-design.md) ·
[Layers contract](../reference/layers.md)

The smallest next improvement is to advance a keyboard-requested menu change
before the presenter leaves that input turn. The largest remaining CPU cost
is committing the new popup geometry and visibility. Cached image transfers
already chain promptly; removing more no-op cache calls would save little.

This analysis reuses the clean CG3 `f68c25c4` package and its existing passive
capture in `build/clipped-menu-text/menus`. Production code is unchanged.
Three complete keyboard and three complete pointer controls retain the same
compiler, ROM, emulator and pixel endpoints. No new guest run was needed.

## Where the time goes

The representative warm File → View keyboard switch, `complete/keyboard/0`,
reaches complete sampled feedback at **100.288 ms**. It charges **66.378 ms**
to the presenter, **14.291 ms** to native interrupts on that Task, and
**19.619 ms** off the presenter. These are disjoint timeline categories;
off-presenter time is not a measurement of DMA or competing application work.

The popup/background transfers restore 4,104/8,960 bytes, with no cache miss,
Files repaint or timed disk activity. The CPU budget below subtracts selected
nested spans before adding categories:

| Work | Exclusive CPU ms |
| --- | ---: |
| Final saved-popup scene commit | 16.470 |
| Title drawing and scratch publication | 9.965 |
| Menu/input advancement and transition control | 8.145 |
| Paint selection and retirement outside drawing | 5.310 |
| Two copy submissions and their completion polls | 5.203 |
| Runnable/readiness decisions | 4.442 |
| Remaining controls, input, publication, cache inspection and worker glue | 16.843 |

The title renderer itself takes 8.124 ms within the 9.965 ms drawing/publication
row. Warm switching does not render the popup's menu entries; the recent
clipped-glyph improvement therefore has little effect here.

Elapsed milestones from the keyboard stimulus:

| Milestone | ms |
| --- | ---: |
| Heading-change key handled | 9.991 |
| Next menu advancement begins | 16.998 |
| Background copy submission begins | 20.397 |
| Background blitter completion | 24.410 |
| Popup copy submission begins | 27.421 |
| Popup blitter completion | 30.381 |
| Replacement geometry/visibility committed | 55.384 |
| Title repaint retired | 77.992 |
| First complete matching frame sample | 100.288 |

The second copy starts **0.960 ms after the first completion poll returns**.
The two hardware completion-to-poll-return intervals are 2.052 and 4.280 ms.
These include software service and interrupt timing; they are not evidence
of a busy-wait loop. The completion path is notification driven, and the
foreground continuation already runs before ordinary controls.

The final frame bracket is **80.079–100.288 ms**. Importantly, 7.144 ms of the
66.378 ms presenter charge occurs *after* title retirement. That housekeeping
is useful CPU work to reduce, but it must not all be presented as delaying the
draw. Presenter CPU up to title retirement is 59.234 ms. Future comparisons
should keep both that endpoint and the complete pixel-frame bracket.

## Keyboard input arrives after its advancement point

The worker currently performs
`DESKINPUT.Service → DESKINPUT.Advance → DESKPAINT.Sync → CONSOLEINPUT.Service`.
The last call drains keyboard events and reaches `DESKMENU.Key`, which queues
the heading change. Its normal advancement opportunity has already passed.
With no existing paint, `DESKPAINT.Pump` returns zero and the worker completes
its tail, yields, and starts another turn before launching the restore.

All three complete keyboard samples show this sequence:

| Sample | Key return → next menu advance | Presenter CPU in that interval |
| --- | ---: | ---: |
| 0 | 7.008 ms | 5.688 ms |
| 1 | 7.916 ms | 6.499 ms |
| 2 | 7.007 ms | 5.689 ms |

No time in these intervals is charged to another Task. This is a service-order
issue, not observed application contention. Mouse capture is serviced before
`DESKINPUT.Advance`, so this particular delay does not apply to pointer changes.

The first refactor should give a newly queued keyboard menu operation one
advancement opportunity before paint/output selection. Reuse `DESKMENU.Advance`
and its existing gates and two-transaction fairness allowance. Preserve the
existing ordering of native controls, pointer focus, drag and widget commits;
moving all gesture advancement or keyboard routing would change more than
necessary. Do not renew the input, control or paint budgets.

The measured interval is an opportunity, not a promised 7–8 ms saving: some of
its service work remains necessary, and earlier DMA can overlap it. Confirm
the new ordering and completion time with the same keyboard/pointer controls.

Source: [worker input order](../../lib/console/consoledriver.act),
[key queue and advancement](../../lib/desktop/deskmenu.act),
[gesture ordering](../../lib/desktop/deskinput.act).

## An empty paint pass still searches the scene

Before that queued heading is advanced, `DESKPAINT.Pump` spends **1.613 ms CPU**
finding no candidate. It probes the menu layers and focused window, rotates
through every layer slot, then probes menus again. The existing
`scene.visibleDamage` summary already supplies the empty answer.

When there is no active paint token and the summary is zero, return before
candidate selection. An active token must still run to retire its transaction;
ordinary candidate order and fairness remain unchanged when damage exists.
This uses existing state and requires no new scheduling mechanism.

This 1.613 ms lies inside the keyboard interval above. It must not be added to
that interval as an independent saving. The guard also helps other empty
paint calls, while an earlier keyboard advance may itself eliminate this
particular scan.

Source: [paint selection](../../lib/desktop/deskpaint.act).

## Scene retirement remains the larger shared target

`FinishSavedReplace` costs **16.470 ms CPU**, including one **11.308 ms**
`Rebuild`. The rebuild executes ten region subtractions and updates damage
summaries for all nine layer slots. Its damage scans alone take 2.252 ms.
There is already only one rebuild; the previous duplicate rebuilds are gone.

Outside the rebuild, the remaining 5.161 ms covers restored-damage retirement,
geometry publication, lookup and transaction cleanup. There are 24 rectangle
intersections before rebuilding. `SubtractDamage` processes dirty lists through
shared scratch even for disjoint entries, and copies the resulting list back.

Two bounded follow-ups are worth investigating:

- Avoid rebuilding damage lists when the restored area intersects none of
  their entries. Retain unchanged records directly where possible. Preserve
  capacity-failure behavior and unrelated damage.
- For a geometry-only popup replacement, recompute visibility only for the
  popup and lower layers intersecting its old or new bounds. Layers above it,
  and layers disjoint from both bounds, retain valid visibility. Update every
  damage summary that actually changed, and publish the existing rebuild
  revision once. Keep the general rebuild for other mutations.

The latter needs a focused Layers plan and independent visibility/damage
checks. The current trace measures the whole rebuild, not the saving from an
affected-layer algorithm. **11.308 ms is not an established removable cost.**
The scene must remain coherent before releasing the token or allowing clients
to draw; pixel caching does not make the visibility update optional.

Source: [saved replacement](../../lib/display/layers-save.inc),
[damage subtraction](../../lib/display/layers-repaint.inc),
[visibility rebuild](../../lib/display/layers.act).

## Small costs and priorities

Six cache-pump calls look conspicuous, but the four that do no work cost only
**0.028 ms combined**. Their two productive calls contain the copy continuation
and scene commit. Reducing the call count alone would miss the actual cost.
The complete feedback traces contain no `FindTask(NULL)` call.

After a successful restore, idle cache inspection may still enter
`CapturePopup`, calculate bounds and find that this exact image is already
cached. That call costs **0.822 ms** in the representative sample. Reusing the
existing capture-attempt hint after a clean restore could suppress it without
changing cache validity. It occurs after title retirement, so it is a secondary
CPU cleanup, not the first foreground-latency change. Failed/stale restores and
new menu revisions must retain their current retry behavior.

Recommended next slice: the keyboard advancement order and empty-paint guard,
followed by a matched complete-feedback check. Keep cache capacity, painter
strip size, kernel scheduling and interrupt policy unchanged. Then address
saved-replacement damage/visibility work with its own focused plan if the
remaining latency warrants it. Adding a third popup slot concerns cold misses
and cannot improve these already cached transitions.

## Evidence and validation

The compact record retains the six individual controls, exact frame brackets,
copy milestones, relevant inclusive routine costs and the disjoint CPU budget.
Ownership/IRQ intervals were recomputed from the existing passive markers and
agree with the original complete-feedback measurements. No p95 claim follows
from three samples, and no timing saving has been demonstrated for the proposed
refactor.

This is documentation and trace analysis only. Content, JSON consistency and
local links are checked; no build or additional emulator/test matrix ran.
Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. No production memory or code changed.
