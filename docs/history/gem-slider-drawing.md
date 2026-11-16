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

## Selected scrollbar object

Changed horizontal/vertical size and position setters now use the existing
track geometry for both invalidation and visible paint clips. The paint object
includes its outside frame edge; arrow cells, info text and the corner remain
outside it. UPDATE, caller execution, the GEM4XE frame raster, physical grant
and completion fences retain their existing flow. Equal setters still draw
nothing. Iconified setters retain metadata without invalidating an unlinked
track. MGVIEW, Counter and their APPs are unchanged.

The distinction between hit geometry and paint geometry matters on packed
VBXE pixels. The first experiment used the hit range literally, excluding the
outer edge and creating an odd X cut. Fills fell from 20 to 10, but added mask
work absorbed most of that saving: the slider still charged about 39.1 ms.
The shipped object includes its frame edge, avoiding that new cut while still
excluding arrows and the corner. It needs 13 fills and two rejected gadget
calls rather than 20 fills and five gadget calls. Command submissions remain
three; their total CPU cost falls. Visibility clipping can still produce odd
edges, handled by the existing raster path.

| Charged CPU (ms) | Down before | Down after | Up before | Up after |
| --- | ---: | ---: | ---: | ---: |
| Slider helper | 39.31 | 32.57 | 39.40 | 32.98 |
| Caller frame painting, included above | 21.75 | 14.25 | 21.84 | 14.29 |
| Whole `set_shift` | 125.23 | 121.43 | 125.91 | 121.74 |

The helper's elapsed time falls from 58.71/58.82 to 48.95/49.34 ms. Whole
`set_shift` elapsed falls from 179.60/180.50 to 173.48/173.66 ms. Viewport
completion remains frame-polled: observed upper bounds change from
143.82/176.92 to 157.18/157.16 ms. Their brackets overlap, so these samples
do not establish a consistent visible-latency improvement. UPDATE Attempts
still succeed without an Obtain wait. END_UPDATE remains about 38 ms CPU;
the additional owner-copy call lies inside `DESKCACHE.Capture`, whose existing
path copies the window's outer bounds. That policy is unchanged here.

The focused optimized frame fixture passes 223 C and four native assertions
across 36 checkpoints: both axes, ordinary/PB, held/unheld, equal and invalid
values, hidden/iconified windows, overlap and exact frame/menu pixels. Two
added assertions cover slider values while iconified. Its startup expectations
also follow SM4's caller admission: open establishes a grant, then equal setters
reuse it. The first run's four obsolete no-grant assertions failed despite all
36 pixel checkpoints matching; the corrected fixture passes with current
expectations. The loaded down/up case passes exact viewport pixels, one
viewport copy and exposed-row draw per
action, Counter progress, all four Process retirements and every stack/guard
check. Host checks pass 718 tests with five existing skips. The
[delivery evidence](../development/gem-slider-drawing.json) records the actual
images, source hashes, CPU phases, sampling limits and stack observations.

Reserved bank-zero growth remains **0 fixed, root, kernel, idle and per public
Task**, counting DP, guards, alignment and spare capacity. No new upper-memory
record or reservation, Task, signal, platform service, public/wire ABI, VRAM or
physical scratch is introduced. These are focused development checks, with no
QED, catalog, demo refresh or raw/release matrix.
