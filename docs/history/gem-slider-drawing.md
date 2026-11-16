# Caller slider drawing costs

[History index](README.md) · [AES contract](../reference/aes.md) ·
[SCRENMGR acceptance](screnmgr-migration.md#sm5b-loaded-acceptance-and-caller-workspace-headroom)

## Baseline audit

The passive `measure_mgview.py --presenter --slider` observer reuses the exact
SM5 native image and unchanged ABI-46 MGVIEW/Counter APPs. It traces emitted
entry/return PCs for caller mutation, thumb geometry, view/input publication,
frame painting, command construction and driver work. Innermost selected
routine intervals partition charged CPU; inclusive routine totals overlap.
No guest instrumentation, reservation or ABI changes are involved.

Both down/up actions pass exact viewport pixels, one viewport copy, exposed-row
drawing, Counter progress, complete Process cleanup and stack/guard checks.
The [baseline evidence](../development/gem-slider-baseline.json) pins the
compiler/machine inputs and observed images. The slider helper takes
39.31/39.40 ms CPU. Caller frame painting accounts for 21.75/21.84 ms, including
20 widget fills, five gadget calls and three command submissions per action.
Input snapshot publication accounts for 4.71 ms. The remaining phases are
recorded separately rather than attributed to UPDATE contention; all three
native UPDATE Attempts succeed in each action.

Pinned MagiC AESWIN `ws_slend` (2768–2794) changes the selected axis through
`_wbm_sslid`, then calls `wind_draw` on `O_VSCROLL` or `O_HSCROLL`. The frame
layout (1116–1197) excludes arrow cells from those track objects. Pinned GEM4XE
`src/aes/wind.c` likewise selects `W_VSLIDE`/`W_HSLIDE` for changed size/position
and draws that subtree (1237–1273). Exec currently invalidates and redraws the
whole side/bottom rail, including arrows and the corner. The next bounded
change is to use the existing track geometry for invalidation and visible
frame clips, retaining caller execution, UPDATE, physical admission and fences.
No drawing-limit or application-source change is needed.

The trace also corrects SM5b's description of the extra owner-copy call: it
occurs inside `wind_update(END_UPDATE)`, after viewport drawing, rather than
inside the slider helper. The viewport copy remains one checked completion.
END/cache work is a separate follow-up and is not part of the slider change.

Reserved bank-zero growth is **0 fixed, root, kernel, idle and per public Task**,
including guards, alignment and unused capacity. These two observations do
not establish a latency distribution or a performance improvement. No QED,
catalog, demo refresh or release qualification was run.
