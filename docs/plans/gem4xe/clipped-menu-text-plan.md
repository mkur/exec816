# Clipped menu text implementation plan

Status: CG1–CG3 complete, with each executable slice committed after its
focused checks. [Execution record](../../history/clipped-menu-text.md) ·
[Measurements](../../development/clipped-menu-text.json).

[Menu response results](../../history/menu-title-response.md) ·
[Existing text plan](text-run-fast-path-plan.md) ·
[Development testing policy](../../contributing/testing.md)

Make uncached dropdown text cheaper by extending the existing VRAM glyph-run
encoder to vertical clipping. Keep the current menu geometry, 16-row scratch
strips, four-object/80-character menu budget, Layers transactions and normal
preemption. No additional popup cache, public API or scheduling mechanism is
needed for this work.

## Starting evidence

The preserved MT3 package is `build/menu-title-response/demo`; its trace is
`build/menu-title-response/menus/menu-analysis.json`. The representative
`keyboard/heading/1` action opens the uncached Desk menu and reaches its
historical sampled pixel endpoint at 240.743 ms. That observer compares
rows 32–207; it is not the complete popup-and-heading endpoint added in MT1.

Six popup paint calls consume 114.408 ms presenter CPU; a separate heading
paint consumes 7.965 ms. Partitioning the popup spans without double counting
nested calls gives:

| Popup work | CPU ms |
| --- | ---: |
| Text processing outside masked-command construction and submission | 34.351 |
| Generic masked-command construction | 27.447 |
| Object traversal, layout and other batch work | 27.121 |
| Submission and fences | 17.245 |
| Fills | 6.207 |
| Outer Action/C call overhead | 2.036 |

The popup submits 283 records in 11 lists. No pixel uploads through
`VbxeOwnerWrite` occur inside these paint calls; font masks already reside in
VRAM. List uploads and synchronization remain part of submission costs.

The 11-pixel menu-row spacing crosses the presenter's 16-row strip boundaries.
`GemWidgetText` admits the fast run only when all eight glyph rows fit. A
vertical cut therefore falls back to `dev_glyph` for every character. At odd X,
the clipped renderer emits left-edge, right-edge and middle records for each
partial glyph, even when the character is horizontally complete.

| Split label | Current records across both strips | Projected records |
| --- | ---: | ---: |
| New Window | 54 | 18 |
| Text | 24 | 8 |
| Counter | 42 | 14 |
| Quit Desktop | 66 | 22 |
| Total | 186 | 62 |

Those eight partial-label calls cost 55.938 ms CPU inclusive. Using one record
per visible nonblank glyph portion projects 283 → 159 popup records, about
44% fewer. This predicts command count, not a latency reduction; fills, source
traversal, strip publication and presenter work remain.

## CG1 Extend the private glyph-run encoder

Implemented. All 37 optimized pixel stages pass, including 72 partial-run
combinations, mixed-list limits and failure recovery. Aggregate visible-row
work uses the existing work table once per prefix, avoiding a per-glyph tally.

Change `ports/gem4xe/adapter/gem-vbxe.c` and the maintained donor integration
patch `ports/gem4xe/patches/0007-widget-glyph-runs.patch`. Edit extraction inputs,
not generated build copies, and rebuild every private caller together.

- Allow a run to select a first atlas row and one through eight visible rows.
  Compute the atlas row offset and destination once per run. Retain the
  existing even-X four-byte and odd-X five-byte atlases and blank-glyph map.
- Generalize the record encoder's height while preserving its compact writes.
  A horizontally complete nonzero-ink glyph needs one stencil record at either
  parity: transparent padding in the odd atlas preserves adjacent nibbles.
  Do not add per-glyph geometry validation or a second rasterization path.
- Keep the existing full-height callers passing row zero and height eight in
  this slice. Maintain one shared private implementation; no public ABI or
  Action/C packet layout changes are required.
- Reserve a run prefix with the existing 96/120-unit capacity tables as a
  conservative bound. Calculate the actual visible-row cost once per run,
  accumulate it for emitted records, and publish count/work once per prefix.
  Blanks consume neither records nor work. Do not add division, remainder,
  runtime table generation or a new bank of capacity tables. A conservative
  prefix may leave a small amount of capacity unused; measure actual drains.
- Preserve record/work limits, mixed fill/text order, scratch redirection,
  staging dependencies and fault latching. A blank-only suffix must not launch
  a full queue. No reserved prefix survives a callback or public return.

Extend the existing builder probe and widget pixel fixture with direct partial
runs. Check both parities, visible rows at the top/middle/bottom of the atlas,
spaces, an almost-full mixed list, work exhaustion and a failed submission.
Check pixels against the independent font oracle and verify record counts and
work bounds from emitted lists. Retain the existing full-height run cases.

Completion: the private encoder draws clipped row spans correctly with one
record per nonblank glyph portion, and existing full-height callers still pass.

Commit: `Support vertical clipping in the glyph run encoder`.

## CG2 Route clipped widget and menu text through runs

Implemented. All 38 optimized pixel stages and the AES-menu fixture pass,
including the long checked/disabled odd-X menu and partial-row oracle.

Change `ports/gem4xe/hosted/hosted-dispatch.inc::GemWidgetText` and the private
donor run wrapper. Reuse the renderer for menu, widget and frame callers.

- Intersect the eight-row glyph cell with the admitted vertical clip once.
  Return without drawing when it is empty. Compute first source row, visible
  height and destination Y, then admit horizontally complete cells to the run
  even when fewer than eight rows remain.
- Preserve left/right partial-cell drawing through the existing clipped-glyph
  fallback. Handle a single cell cut on both sides once; retain signed input
  coordinates and screen-edge behavior.
- Preserve the hardware-zero-ink fallback and current transparent drawing
  semantics. Retain workstation save/restore, selected and disabled object
  composition, checkmarks and the original drawing order.
- Keep scratch publication after a complete strip, failure damage retention,
  frozen menu source state and input boundaries. Do not enlarge strips, align
  application labels differently or change menu traversal budgets.

Extend `tools/test_widget_pixels.py` and its existing C probes for vertically
clipped runs at even/odd X, combined horizontal/vertical cuts, one visible row,
empty clips, blank strings and zero/nonzero ink. Verify neighboring nibbles and
rows remain unchanged. Include selected/disabled composition and continuation
or failure before publication, reusing existing cases where they already cover
the behavior.

Run the optimized AES-menu fixture with the affected long odd-X/clipped label
case and ordinary menu controls. Preserve independent pixel comparisons and
guard/ownership cleanup checks. Inspect emitted calls or passive markers to
confirm vertically clipped complete cells reach the run encoder while genuine
edge cells still use the fallback.

Completion: a split menu label uses one record per visible nonblank glyph
portion, full-height text retains its fast path, and final pixels are unchanged.

Commit: `Keep vertically clipped menu text on the glyph run path`.

## CG3 Measure dropdown response and refresh the demo

Complete. Desk popup records fall 283 → 159 and paint CPU 114.408 → 64.229 ms.
Its historical sampled response improves 240.743 → 180.377 ms; warm complete
feedback is unchanged. The matched 36-action capture, Counter/EXIT checks and
OF816 package checksums pass. The memory reservation manifest is unchanged.

Preserve the MT3 archive and its compiler/ROM/emulator configuration. Reuse its
recorded baseline; do not rebuild it. Extend the passive observer only as needed
to count run versus fallback calls and reconstruct list totals. If new markers
are needed, recapture only the affected actions on the preserved package.

Compare the same File → View → Desk sequence, retaining each menu separately:
the historical three samples visit different headings and are not three
repetitions of Desk. Measure repeated Desk misses under the same cache sequence
if a per-menu distribution is needed. Keep the two-slot cache unchanged and
verify matching misses/restores, no incidental Files paints and no timed disk
traffic.

Report popup paint CPU, text CPU, record/list counts, submission/fence costs,
heading retirement and sampled visible response. Preserve the historical pixel
endpoint and add complete old/new popup footprints plus changed headings for
any new complete-feedback comparison. Do not label the old cropped endpoint as
complete feedback. Use the same observer on both packages, with last-nonmatch
and first-match frames; no p95 claim from small samples.

Confirm the four split labels fall from 186 to 62 records and explain any
difference from the projected 159 total. Require lower popup drawing CPU for
the representative miss and investigate a material full-height/warm-path
regression. A CPU improvement without a visible-frame improvement is recorded
as such. Include one warm switch/highlight/dismiss control and the existing
Counter-progress check; no broad desktop or filesystem matrix is needed.

Build one final desktop demo with `tools/build_demo.py --gem-desktop
--release-compiler`. Include OF816, five-second autoboot, matching system disk,
pinned ROM, guide, licenses and checksums. Keep traces/build intermediates
outside the ZIP. Check normal EXIT, guards and archive checksums. Save compact
measurements in `docs/development`, interpretation in `docs/history`, update
indices and slice status, and provide the demo launch command.

Commit: `Record clipped menu text performance and refresh the demo`.

## Resources and validation

Expected reservation delta for every slice: **0 fixed bank-zero bytes, 0 per
public Task, 0 idle**, including guards, alignment and unused capacity. Reuse
the existing glyph atlas, scratch strip, command buffer and lookup tables;
no VRAM, upper-memory, Scene, DP or stack reservation growth is planned. Record
actual code/data size and local/observed stack changes after implementation.

Use development-tier checks: affected host/extraction checks and focused
optimized emitted pixel, list-budget and failure cases. Raw checks are needed
only if a compiler-facing problem emerges. Reuse passing checks until their
inputs change. This plan does not qualify hardware or establish worst-case
latency bounds. Additional popup slots, strip realignment and visibility
rebuild changes remain separate follow-up decisions.
